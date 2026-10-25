"""
Module: shared_memory.py
Mô tả: Hiện thực cơ chế IPC Shared Memory với kiến trúc Bounded Buffer (Mảng vòng).
       Sử dụng threading.Semaphore và threading.Lock để đồng bộ hóa hoàn toàn.
       Tách biệt khỏi GUI, hỗ trợ cả cơ chế Non-blocking (try_acquire) cho GUI ticker
       lẫn Blocking/Timeout cho Worker Threads mà không gây treo Main Thread.
Task: HDH-24 - Code hoàn thiện và Test luồng lõi Shared Memory (tích hợp Mutex, Semaphore).
Python version: 3.10+
"""

from __future__ import annotations

import threading
import time
from typing import Any
from src.core import log_trace 

from src.core.ipc_interface import IIPCMechanism, IPCResult, IPCStatus
from src.core.ipc_interface import IIPCMechanism, IPCResult, IPCStatus


class SharedMemory(IIPCMechanism):
    """
    Hiện thực cơ chế Shared Memory sử dụng Bounded Buffer (Mảng vòng - Circular Buffer).

    Nguyên lý đồng bộ (Theo lý thuyết Hệ điều hành Silberschatz / Tanenbaum):
    - `mutex` (Binary Semaphore / Lock, khởi tạo = 1): Đảm bảo loại trừ tương hỗ (Mutual Exclusion),
      chỉ cho phép DUY NHẤT một tiến trình/luồng được truy cập và chỉnh sửa Critical Section
      (vùng nhớ đệm, con trỏ in_ptr, out_ptr).
    - `empty` (Counting Semaphore, khởi tạo = capacity): Đếm số lượng ô nhớ trống.
      Khi empty == 0 (Buffer đầy), Producer bắt buộc phải chờ (Wait/BLOCKED).
    - `full` (Counting Semaphore, khởi tạo = 0): Đếm số lượng ô nhớ chứa dữ liệu.
      Khi full == 0 (Buffer rỗng), Consumer bắt buộc phải chờ (Wait/BLOCKED).

    Đặc tính quan trọng phục vụ GUI:
    - Khi Buffer Full hoặc Buffer Empty, nếu gọi với `timeout=0.0` (mặc định), hàm sẽ sử dụng
      `try_acquire` (non-blocking) và trả về ngay lập tức `status="BLOCKED"`.
      Tuyệt đối KHÔNG có vòng lặp `while True` bận (Busy-waiting) gây đông cứng giao diện.
    - Cung cấp hàm `get_state()` trả về snapshot tức thời của bộ đệm và biến đồng bộ.
    """

    def __init__(self, capacity: int) -> None:
        """
        Khởi tạo vùng nhớ chia sẻ với dung lượng `capacity`.

        Args:
            capacity: Số ô nhớ tối đa của Circular Buffer (phải > 0).
        """
        super().__init__(capacity)

        # 1. Cấu trúc dữ liệu Circular Buffer (Mảng vòng)
        self._buffer: list[Any | None] = [None] * self._capacity
        self._in_ptr: int = 0    # Con trỏ ghi (Vị trí Producer ghi dữ liệu kế tiếp)
        self._out_ptr: int = 0   # Con trỏ đọc (Vị trí Consumer đọc dữ liệu kế tiếp)
        self._count: int = 0     # Số phần tử hiện có trong buffer

        # 2. Các biến đồng bộ hóa (Synchronization Primitives)
        # Mutex: Khóa nhị phân bảo vệ Critical Section (ghi/đọc buffer, cập nhật in/out_ptr)
        self._mutex = threading.Lock()

        # Semaphore empty: Đếm số ô trống khả dụng (Ban đầu = capacity)
        self._empty = threading.Semaphore(self._capacity)

        # Semaphore full: Đếm số ô có dữ liệu khả dụng (Ban đầu = 0)
        self._full = threading.Semaphore(0)

        # 3. Quản lý trạng thái và Trace Log (Phục vụ GUI & Thread-safety)
        # Lock nội bộ bảo vệ việc cập nhật thông tin chẩn đoán trạng thái
        self._state_lock = threading.Lock()
        self._blocked_producers: dict[str, float] = {}  # process_id -> timestamp bắt đầu chờ
        self._blocked_consumers: dict[str, float] = {}  # process_id -> timestamp bắt đầu chờ
        self._mutex_holder: str | None = None          # Process đang chiếm giữ Mutex
        self._step_counter: int = 0                    # Đếm số bước thao tác phục vụ trace log

    @property
    def in_ptr(self) -> int:
        """Chỉ số ô nhớ ghi tiếp theo."""
        return self._in_ptr

    @property
    def out_ptr(self) -> int:
        """Chỉ số ô nhớ đọc tiếp theo."""
        return self._out_ptr

    @property
    def count(self) -> int:
        """Số lượng phần tử hiện có trong buffer."""
        return self._count

    @property
    def is_empty(self) -> bool:
        """Kiểm tra buffer có đang rỗng hay không."""
        return self._count == 0

    @property
    def is_full(self) -> bool:
        """Kiểm tra buffer có đang đầy hay không."""
        return self._count >= self._capacity

    def produce(
        self,
        item: Any,
        process_id: str = "Producer",
        timeout: float | None = 0.0,
    ) -> IPCResult:
        """
        Đưa một item vào vùng nhớ chia sẻ (Producer Logic).

        Quy trình chuẩn hệ điều hành:
            wait(empty)  -> chờ có ô trống (tránh Buffer Overflow)
            wait(mutex)  -> khóa vùng nhớ chia sẻ (tránh Race Condition)
            CRITICAL SECTION: ghi item vào buffer[in_ptr], in_ptr = (in_ptr + 1) % capacity
            signal(mutex)-> mở khóa vùng nhớ chia sẻ
            signal(full) -> báo hiệu có thêm 1 ô chứa dữ liệu cho Consumer

        Args:
            item: Dữ liệu cần sản xuất/ghi vào buffer.
            process_id: Định danh tiến trình thực hiện ghi.
            timeout: Thời gian chờ tối đa (giây). 0.0 là non-blocking (GUI safe).

        Returns:
            IPCResult: Kết quả thao tác kèm trạng thái "SUCCESS" hoặc "BLOCKED".
        """
        # =====================================================================
        # GIAI ĐOẠN 1: WAIT(EMPTY) - Kiểm tra và chiếm dụng ô nhớ trống
        # =====================================================================
        is_blocking = (timeout is None) or (timeout > 0.0)

        if not is_blocking:
            # Chế độ Non-blocking (Dành cho GUI ticker/step simulation)
            # Thử chiếm Semaphore empty không chờ: nếu empty == 0 -> buffer đầy
            acquired_empty = self._empty.acquire(blocking=False)
            if not acquired_empty:
                log_trace("WAIT_EMPTY", f"Process: {process_id}")
                
                with self._state_lock:
                    self._blocked_producers[process_id] = time.time()
                # Ghi nhận process bị block vào danh sách theo dõi
                with self._state_lock:
                    self._blocked_producers[process_id] = time.time()

                return IPCResult(
                    status=IPCStatus.BLOCKED.value,
                    data=None,
                    success=False,
                    detail=(
                        f"Buffer ĐẦY ({self._count}/{self._capacity}). "
                        f"[{process_id}] bị BLOCKED tại Semaphore 'empty'."
                    ),
                )
        else:
            # Chế độ Blocking / Timeout (Dành cho Worker Thread)
            with self._state_lock:
                self._blocked_producers[process_id] = time.time()

            # Chờ Semaphore empty (có hoặc không có thời hạn)
            wait_kwargs = {"blocking": True}
            if timeout is not None:
                wait_kwargs["timeout"] = timeout

            acquired_empty = self._empty.acquire(**wait_kwargs)

            if not acquired_empty:
                log_trace("WAIT_EMPTY", f"Process: {process_id} (Timeout)")
                
                with self._state_lock:
                    self._blocked_producers.pop(process_id, None)
                # Hết thời gian timeout mà buffer vẫn đầy
                with self._state_lock:
                    self._blocked_producers.pop(process_id, None)

                return IPCResult(
                    status=IPCStatus.BLOCKED.value,
                    data=None,
                    success=False,
                    detail=(
                        f"[{process_id}] bị BLOCKED (Timeout sau {timeout}s do Buffer đầy)."
                    ),
                )

        # Khi đã chiếm được Semaphore empty thành công, xóa khỏi danh sách blocked
        with self._state_lock:
            self._blocked_producers.pop(process_id, None)

        # =====================================================================
        # GIAI ĐOẠN 2: WAIT(MUTEX) - Vào Critical Section
        # =====================================================================
        # KHÓA MUTEX: Bảo vệ thao tác ghi dữ liệu và dịch con trỏ
        self._mutex.acquire()
        log_trace("LOCK_ACQUIRE", f"Process: {process_id}")
        
        try:
            with self._state_lock:
                self._mutex_holder = process_id

            # --- BẮT ĐẦU CRITICAL SECTION ---
            slot_index = self._in_ptr
            self._buffer[slot_index] = item
            log_trace("WRITE_SLOT", f"Slot: {slot_index}")
            
            self._in_ptr = (self._in_ptr + 1) % self._capacity
            self._count += 1
            self._step_counter += 1
        try:
            with self._state_lock:
                self._mutex_holder = process_id

            # --- BẮT ĐẦU CRITICAL SECTION ---
            slot_index = self._in_ptr
            self._buffer[slot_index] = item
            self._in_ptr = (self._in_ptr + 1) % self._capacity
            self._count += 1
            self._step_counter += 1
            # --- KẾT THÚC CRITICAL SECTION ---

        finally:
            # =================================================================
            # GIAI ĐOẠN 3: SIGNAL(MUTEX) - Rời khỏi Critical Section
            # =================================================================
            with self._state_lock:
                self._mutex_holder = None
            # MỞ KHÓA MUTEX
            self._mutex.release()

        # =====================================================================
        # GIAI ĐOẠN 4: SIGNAL(FULL) - Báo hiệu có dữ liệu cho Consumer
        # =====================================================================
        # Tăng giá trị Semaphore full lên 1, đánh thức Consumer nếu đang ngủ
        self._full.release()

        # Nếu trước đó có consumer nào bị đánh dấu blocked trong chế độ non-blocking,
        # dọn dẹp vì giờ buffer đã có dữ liệu
        with self._state_lock:
            if self._blocked_consumers and self._count > 0:
                # Giải phóng consumer đang chờ lâu nhất
                oldest_consumer = next(iter(self._blocked_consumers.keys()))
                self._blocked_consumers.pop(oldest_consumer, None)

        return IPCResult(
            status=IPCStatus.SUCCESS.value,
            data=item,
            success=True,
            detail=(
                f"[{process_id}] ghi thành công '{item}' vào slot {slot_index}. "
                f"(in_ptr: {slot_index} -> {self._in_ptr}, count: {self._count}/{self._capacity})"
            ),
        )

    def consume(
        self,
        process_id: str = "Consumer",
        timeout: float | None = 0.0,
    ) -> IPCResult:
        """
        Lấy một item ra khỏi vùng nhớ chia sẻ (Consumer Logic).

        Quy trình chuẩn hệ điều hành:
            wait(full)   -> chờ có dữ liệu (tránh Buffer Underflow)
            wait(mutex)  -> khóa vùng nhớ chia sẻ (tránh Race Condition)
            CRITICAL SECTION: item = buffer[out_ptr], xóa ô, out_ptr = (out_ptr + 1) % capacity
            signal(mutex)-> mở khóa vùng nhớ chia sẻ
            signal(empty)-> báo hiệu có thêm 1 ô trống cho Producer

        Args:
            process_id: Định danh tiến trình thực hiện đọc.
            timeout: Thời gian chờ tối đa (giây). 0.0 là non-blocking (GUI safe).

        Returns:
            IPCResult: Kết quả thao tác chứa item hoặc trạng thái "BLOCKED".
        """
        # =====================================================================
        # GIAI ĐOẠN 1: WAIT(FULL) - Kiểm tra và chiếm dụng ô nhớ có dữ liệu
        # =====================================================================
        is_blocking = (timeout is None) or (timeout > 0.0)

        if not is_blocking:
            # Chế độ Non-blocking (Dành cho GUI ticker/step simulation)
            # Thử chiếm Semaphore full không chờ: nếu full == 0 -> buffer rỗng
            acquired_full = self._full.acquire(blocking=False)
            if not acquired_full:
                # Ghi nhận process bị block vào danh sách theo dõi
                with self._state_lock:
                    self._blocked_consumers[process_id] = time.time()

                return IPCResult(
                    status=IPCStatus.BLOCKED.value,
                    data=None,
                    success=False,
                    detail=(
                        f"Buffer RỖNG (0/{self._capacity}). "
                        f"[{process_id}] bị BLOCKED tại Semaphore 'full'."
                    ),
                )
        else:
            # Chế độ Blocking / Timeout (Dành cho Worker Thread)
            with self._state_lock:
                self._blocked_consumers[process_id] = time.time()

            wait_kwargs = {"blocking": True}
            if timeout is not None:
                wait_kwargs["timeout"] = timeout

            acquired_full = self._full.acquire(**wait_kwargs)

            if not acquired_full:
                # Hết thời gian timeout mà buffer vẫn rỗng
                with self._state_lock:
                    self._blocked_consumers.pop(process_id, None)

                return IPCResult(
                    status=IPCStatus.BLOCKED.value,
                    data=None,
                    success=False,
                    detail=(
                        f"[{process_id}] bị BLOCKED (Timeout sau {timeout}s do Buffer rỗng)."
                    ),
                )

        # Khi đã chiếm được Semaphore full thành công, xóa khỏi danh sách blocked
        with self._state_lock:
            self._blocked_consumers.pop(process_id, None)

        # =====================================================================
        # GIAI ĐOẠN 2: WAIT(MUTEX) - Vào Critical Section
        # =====================================================================
        # KHÓA MUTEX: Bảo vệ thao tác đọc dữ liệu và cập nhật con trỏ
        self._mutex.acquire()
        log_trace("LOCK_ACQUIRE", f"Process: {process_id}")
        try:
            with self._state_lock:
                self._mutex_holder = process_id

            # --- BẮT ĐẦU CRITICAL SECTION ---
            slot_index = self._out_ptr
            item = self._buffer[slot_index]
            log_trace("READ_SLOT", f"Slot: {slot_index}")
            self._buffer[slot_index] = None  # Xóa sạch ô nhớ sau khi đọc (Clear slot)
            self._out_ptr = (self._out_ptr + 1) % self._capacity
            self._count -= 1
            self._step_counter += 1
            # --- KẾT THÚC CRITICAL SECTION ---

        finally:
            # =================================================================
            # GIAI ĐOẠN 3: SIGNAL(MUTEX) - Rời khỏi Critical Section
            # =================================================================
            with self._state_lock:
                self._mutex_holder = None
            # MỞ KHÓA MUTEX
            self._mutex.release()

        # =====================================================================
        # GIAI ĐOẠN 4: SIGNAL(EMPTY) - Báo hiệu có thêm ô trống cho Producer
        # =====================================================================
        # Tăng giá trị Semaphore empty lên 1, đánh thức Producer nếu đang chờ
        self._empty.release()

        # Nếu trước đó có producer bị đánh dấu blocked trong non-blocking mode,
        # dọn dẹp vì giờ buffer đã có chỗ trống
        with self._state_lock:
            if self._blocked_producers and self._count < self._capacity:
                oldest_producer = next(iter(self._blocked_producers.keys()))
                self._blocked_producers.pop(oldest_producer, None)

        return IPCResult(
            status=IPCStatus.SUCCESS.value,
            data=item,
            success=True,
            detail=(
                f"[{process_id}] đọc thành công '{item}' từ slot {slot_index}. "
                f"(out_ptr: {slot_index} -> {self._out_ptr}, count: {self._count}/{self._capacity})"
            ),
        )

    def get_state(self) -> dict[str, Any]:
        """
        Lấy snapshot trạng thái toàn diện của vùng nhớ chung để GUI vẽ Canvas/Graphics.

        Đảm bảo Thread-safe khi lấy dữ liệu mà không làm gián đoạn các luồng khác.

        Returns:
            dict bao gồm:
                - "buffer": Bản sao (shallow copy) của mảng dữ liệu Circular Buffer.
                - "in_ptr": Vị trí con trỏ ghi in_ptr.
                - "out_ptr": Vị trí con trỏ đọc out_ptr.
                - "mutex": Giá trị Mutex (1: Unlocked/Sẵn sàng, 0: Locked/Đang bị chiếm).
                - "empty": Giá trị Semaphore empty (Số ô trống còn lại).
                - "full": Giá trị Semaphore full (Số ô có dữ liệu).
                - "blocked_processes": Danh sách tên các tiến trình đang bị block.
                - "capacity": Dung lượng tối đa của buffer.
                - "count": Số phần tử hiện có trong buffer.
                - "mutex_holder": Tiến trình đang giữ Mutex (hoặc None).
                - "step": Số thứ tự thao tác tích lũy (phục vụ Trace log).
        """
        with self._state_lock:
            # Danh sách tất cả process đang bị kẹt tại Semaphore empty hoặc full
            blocked_list = list(self._blocked_producers.keys()) + list(self._blocked_consumers.keys())

            # Chuẩn hóa giá trị Mutex theo toán học OS: 1 là Free, 0 là Busy
            mutex_val = 0 if self._mutex.locked() else 1

            # Giá trị Counting Semaphores bất biến theo số lượng phần tử
            empty_val = self._capacity - self._count
            full_val = self._count

            return {
                "buffer": list(self._buffer),
                "in_ptr": self._in_ptr,
                "out_ptr": self._out_ptr,
                "mutex": mutex_val,
                "empty": empty_val,
                "full": full_val,
                "blocked_processes": blocked_list,
                "capacity": self._capacity,
                "count": self._count,
                "mutex_holder": self._mutex_holder,
                "step": self._step_counter,
            }

    def reset(self) -> None:
        """
        Thiết lập lại toàn bộ trạng thái về ban đầu (Dùng cho nút Reset trên GUI hoặc Re-run test).
        """
        with self._state_lock:
            # Nếu mutex đang bị lock, giải phóng
            if self._mutex.locked():
                try:
                    self._mutex.release()
                except RuntimeError:
                    pass

            self._buffer = [None] * self._capacity
            self._in_ptr = 0
            self._out_ptr = 0
            self._count = 0
            self._step_counter = 0
            self._blocked_producers.clear()
            self._blocked_consumers.clear()
            self._mutex_holder = None

            # Khởi tạo lại semaphores
            self._mutex = threading.Lock()
            self._empty = threading.Semaphore(self._capacity)
            self._full = threading.Semaphore(0)
