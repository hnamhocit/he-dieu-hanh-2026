"""
Module: ipc_interface.py
Mô tả: Định nghĩa Abstract Base Class (Interface) cho các cơ chế IPC (Inter-Process Communication).
Task: HDH-22 - Thiết kế kiến trúc trừu tượng cho Core IPC.
Python version: 3.10+
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any
import queue
from multiprocessing import Queue

class IPCStatus(str, Enum):
    """Trạng thái thực thi của các thao tác IPC."""
    SUCCESS = "SUCCESS"    # Thao tác thành công, không bị nghẽn
    BLOCKED = "BLOCKED"    # Thao tác bị nghẽn (Buffer đầy khi Produce hoặc rỗng khi Consume)
    TIMEOUT = "TIMEOUT"    # Hết thời gian chờ (khi sử dụng cơ chế timeout)
    ERROR = "ERROR"        # Xảy ra lỗi bất thường trong quá trình thực thi


@dataclass
class IPCResult:
    """
    Đối tượng chuẩn hóa kết quả trả về từ các hàm `produce` và `consume`.
    
    Được thiết kế linh hoạt cho cả GUI và Worker Thread:
    - Thuộc tính trực tiếp: result.status, result.data, result.success, result.detail
    - So sánh nhanh với chuỗi: `result == "BLOCKED"`, `result == "SUCCESS"`
    - Đánh giá dạng boolean: `if result:` (True nếu success)
    - Unpack dạng Tuple: `status, item = result`
    """
    status: str
    data: Any | None = None
    success: bool = True
    detail: str = ""

    @property
    def is_blocked(self) -> bool:
        """Kiểm tra xem thao tác có rơi vào trạng thái blocked hay không."""
        return self.status == IPCStatus.BLOCKED.value

    @property
    def item(self) -> Any | None:
        """Alias truy cập nhanh đến item dữ liệu (dùng cho consume)."""
        return self.data

    def __bool__(self) -> bool:
        """Cho phép kiểm tra: `if result:` tương đương `if result.success:`."""
        return self.success

    def __eq__(self, other: Any) -> bool:
        """
        Hỗ trợ so sánh trực tiếp:
        - `result == "BLOCKED"`
        - `result == "SUCCESS"`
        - `result == True / False`
        - `result == expected_item` (khi thao tác thành công)
        """
        if isinstance(other, str):
            return self.status == other
        if isinstance(other, bool):
            return self.success == other
        if self.success and self.data is not None and self.data == other:
            return True
        return super().__eq__(other)

    def __iter__(self):
        """Hỗ trợ unpack cú pháp: `status, item = result`."""
        yield self.status
        yield self.data

    def __str__(self) -> str:
        if not self.success:
            return self.status
        return str(self.data) if self.data is not None else self.status

    def __repr__(self) -> str:
        return (
            f"IPCResult(status='{self.status}', success={self.success}, "
            f"data={self.data!r}, detail='{self.detail}')"
        )


class IIPCMechanism(ABC):
    """
    Abstract Class định nghĩa giao diện chuẩn cho tất cả các cơ chế IPC
    (Shared Memory, Pipe, Message Queue).
    
    Đảm bảo:
    - Tách biệt hoàn toàn tầng thuật toán cốt lõi khỏi GUI (Decoupled Core).
    - Không làm treo luồng chính (Non-blocking / Thread-safe).
    - Cung cấp snapshot trạng thái tức thời cho GUI render qua `get_state()`.
    """

    @abstractmethod
    def __init__(self, capacity: int) -> None:
        """
        Khởi tạo cơ chế IPC với dung lượng đệm nhất định.

        Args:
            capacity: Sức chứa tối đa của bộ đệm (phải > 0).
        """
        if capacity <= 0:
            raise ValueError(f"Dung lượng đệm (capacity) phải lớn hơn 0, nhận giá trị: {capacity}")
        self._capacity: int = capacity

    @property
    def capacity(self) -> int:
        """Dung lượng tối đa của bộ đệm."""
        return self._capacity

    @abstractmethod
    def produce(
        self,
        item: Any,
        process_id: str = "Producer",
        timeout: float | None = 0.0,
    ) -> IPCResult:
        """
        Thêm một item vào bộ đệm (Producer logic).

        Args:
            item: Dữ liệu cần đẩy vào bộ đệm.
            process_id: Định danh tiến trình/luồng gọi produce (mặc định: "Producer").
            timeout: 
                - 0.0: Non-blocking (dành cho GUI ticker/step-by-step). Nếu buffer đầy, 
                       trả về ngay cờ "BLOCKED" mà không đóng băng luồng.
                - > 0.0: Chờ tối đa `timeout` giây rồi trả về "BLOCKED" nếu hết giờ.
                - None: Chờ vô hạn (blocking truyền thống cho luồng nền/worker).

        Returns:
            IPCResult: Chứa trạng thái ('SUCCESS', 'BLOCKED', 'TIMEOUT'), cờ success,
                       và mô tả chi tiết thao tác.
        """
        pass

    @abstractmethod
    def consume(
        self,
        process_id: str = "Consumer",
        timeout: float | None = 0.0,
    ) -> IPCResult:
        """
        Lấy một item ra khỏi bộ đệm (Consumer logic).

        Args:
            process_id: Định danh tiến trình/luồng gọi consume (mặc định: "Consumer").
            timeout:
                - 0.0: Non-blocking (dành cho GUI ticker/step-by-step). Nếu buffer rỗng,
                       trả về ngay cờ "BLOCKED" mà không đóng băng luồng.
                - > 0.0: Chờ tối đa `timeout` giây rồi trả về "BLOCKED" nếu hết giờ.
                - None: Chờ vô hạn (blocking truyền thống cho luồng nền/worker).

        Returns:
            IPCResult: Chứa item (data), trạng thái ('SUCCESS', 'BLOCKED', 'TIMEOUT'),
                       cờ success, và mô tả chi tiết.
        """
        pass

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """
        Lấy snapshot toàn bộ trạng thái hiện tại của bộ đệm để GUI vẽ đồ họa.

        Returns:
            dict chứa các khóa bắt buộc:
                - "buffer": list chứa các phần tử hiện tại trong mảng đệm (hoặc None nếu ô trống).
                - "in_ptr": vị trí ghi tiếp theo (int).
                - "out_ptr": vị trí đọc tiếp theo (int).
                - "mutex": trạng thái khóa Mutex (1: mở/unlocked, 0: đang giữ/locked).
                - "empty": số lượng ô trống hiện có (giá trị Semaphore empty).
                - "full": số lượng ô chứa dữ liệu hiện có (giá trị Semaphore full).
                - "blocked_processes": danh sách định danh các process đang bị block.
        """
        pass