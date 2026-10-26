"""
Module: message_queue.py
Mô tả: Hiện thực cơ chế IPC Message Queue (Hàng đợi thông điệp).
       Kế thừa trực tiếp Interface IIPCMechanism (src/core/ipc_interface.py).
       Hỗ trợ cả cơ chế FIFO lẫn Priority Queue, an toàn đa luồng bằng Monitor
       (threading.Lock + hai Condition Variable `not_full` và `not_empty`).
       Cung cấp API non-blocking (timeout=0.0) cho GUI và blocking/timeout cho Worker.
Tasks: HDH-14, HDH-15, HDH-27, HDH-28, HDH-29, HDH-88
Python version: 3.10+
"""

from __future__ import annotations
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

from src.core.ipc_interface import IIPCMechanism, IPCResult, IPCStatus


@dataclass
class MessagePacket:
    """
    Cấu trúc khuôn mẫu của một gói tin (MessagePacket) theo đặc tả HDH-13.

    Thuộc tính `sequence` (HDH-88) là số thứ tự tăng dần được gán tại thời điểm gói tin
    vào hàng đợi, dùng để phân xử hòa khi nhiều gói tin có cùng mức `priority`.
    """
    id: int
    sender: str
    receiver: str
    message: str = ""
    delay_ms: int = 0
    priority: int = 0
    simulate_error: str = "NONE"
    mechanism: str = "MESSAGE_QUEUE"
    timestamp: float = 0.0
    sequence: int = 0

    def __post_init__(self) -> None:
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        self.payload_size_bytes = len(self.message.encode("utf-8"))

    def to_dict(self) -> dict[str, Any]:
        """Chuyển đổi thành dictionary phục vụ serialization hoặc GUI render."""
        return {
            "id": self.id,
            "sender": self.sender,
            "receiver": self.receiver,
            "message": self.message,
            "delay_ms": self.delay_ms,
            "priority": self.priority,
            "simulate_error": self.simulate_error,
            "mechanism": self.mechanism,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "payload_size_bytes": getattr(self, "payload_size_bytes", len(self.message.encode("utf-8"))),
        }

    def __lt__(self, other: Any) -> bool:
        """
        Quan hệ thứ tự trong Priority Queue: gói tin nào "nhỏ hơn" sẽ được lấy ra trước.

        Quy tắc (Tie-breaking policy):
            1. `priority` lớn hơn thì xếp trước (số lớn = ưu tiên cao hơn).
            2. Cùng `priority` thì `sequence` nhỏ hơn (vào hàng đợi trước) xếp trước (FIFO).
        """
        if not isinstance(other, MessagePacket):
            return NotImplemented
        return (-self.priority, self.sequence) < (-other.priority, other.sequence)


class MessageQueue(IIPCMechanism):
    """
    Hiện thực lõi hàng đợi tin nhắn (Message Queue Core) kế thừa trực tiếp IIPCMechanism.

    Nguyên lý đồng bộ (Monitor Pattern):
    - `mutex`: threading.Lock bảo vệ vùng Critical Section của hàng đợi tin nhắn.
    - `not_full`: Condition Variable báo hiệu khi hàng đợi có chỗ trống (Consumer notify).
    - `not_empty`: Condition Variable báo hiệu khi hàng đợi có tin nhắn mới (Producer notify).
    - Hai Condition Variable dùng chung `mutex`.

    Chế độ hàng đợi:
    - FIFO (mặc định): gói tin vào sau xếp cuối hàng đợi.
    - Priority (`is_priority=True`): gói tin có `priority` cao hơn xếp trước; cùng `priority`
      thì gói tin vào hàng đợi trước được lấy ra trước (tie-breaking FIFO, HDH-88).
    """

    def __init__(self, capacity: int, is_priority: bool = False) -> None:
        """
        Khởi tạo hàng đợi tin nhắn với dung lượng `capacity`.

        Args:
            capacity: Số gói tin tối đa hàng đợi có thể chứa (phải > 0).
            is_priority: True nếu kích hoạt chế độ hàng đợi ưu tiên (Priority Queue).
        """
        super().__init__(capacity)
        self._is_priority: bool = is_priority
        self._queue: list[MessagePacket] = []
        self._seq_counter: int = 0  # Bộ đếm sequence, chỉ thay đổi khi đang giữ mutex

        # Đồng bộ hóa bằng Monitor (Lock + Condition Variables)
        self._mutex = threading.Lock()
        self._not_full = threading.Condition(self._mutex)
        self._not_empty = threading.Condition(self._mutex)

        # Quản lý chẩn đoán và trạng thái (Phục vụ GUI snapshot & Trace log)
        self._state_lock = threading.Lock()
        self._blocked_producers: dict[str, float] = {}
        self._blocked_consumers: dict[str, float] = {}

    @property
    def is_priority(self) -> bool:
        """Chế độ hàng đợi ưu tiên có đang bật hay không."""
        return self._is_priority

    @property
    def count(self) -> int:
        """Số lượng gói tin hiện có trong hàng đợi."""
        with self._mutex:
            return len(self._queue)

    @property
    def is_empty(self) -> bool:
        """Kiểm tra hàng đợi có đang rỗng hay không."""
        with self._mutex:
            return len(self._queue) == 0

    @property
    def is_full(self) -> bool:
        """Kiểm tra hàng đợi có đang đầy hay không."""
        with self._mutex:
            return len(self._queue) >= self._capacity

    def produce(
        self,
        item: Any,
        process_id: str = "Producer",
        timeout: float | None = 0.0,
    ) -> IPCResult:
        """
        Đẩy một thông điệp (MessagePacket) vào hàng đợi.

        Args:
            item: Gói tin MessagePacket hoặc dict/chuỗi (sẽ tự động đóng gói thành MessagePacket).
            process_id: Định danh tiến trình gửi (phục vụ trace log).
            timeout:
                - 0.0: Non-blocking (cho GUI/step-by-step). Nếu đầy, trả về ngay "BLOCKED".
                - > 0.0: Chờ tối đa `timeout` giây, hết hạn thì trả về "TIMEOUT".
                - None: Blocking vô hạn (chờ cho tới khi có chỗ trống).

        Returns:
            IPCResult: Trạng thái SUCCESS (kèm gói tin đã gửi), BLOCKED hoặc TIMEOUT.
        """
        packet = self._normalize_packet(item, process_id)
        start_time = time.time()

        with self._not_full:
            try:
                # 1. Chờ cho đến khi hàng đợi có chỗ trống
                while len(self._queue) >= self._capacity:
                    if timeout == 0.0:
                        return IPCResult(
                            status=IPCStatus.BLOCKED.value,
                            success=False,
                            detail=f"Hàng đợi tin nhắn đã đầy ({len(self._queue)}/{self._capacity}).",
                        )
                    if timeout is not None:
                        remaining = timeout - (time.time() - start_time)
                        if remaining <= 0:
                            return IPCResult(
                                status=IPCStatus.TIMEOUT.value,
                                success=False,
                                detail=f"Quá thời gian chờ ghi ({timeout}s) do hàng đợi đầy.",
                            )
                        with self._state_lock:
                            self._blocked_producers[process_id] = start_time
                        self._not_full.wait(timeout=remaining)
                    else:
                        with self._state_lock:
                            self._blocked_producers[process_id] = start_time
                        self._not_full.wait()
            finally:
                # Dù thành công hay thất bại, tiến trình không còn bị chặn
                with self._state_lock:
                    self._blocked_producers.pop(process_id, None)

            # 2. Gán sequence (đang giữ mutex nên giá trị là duy nhất) rồi đưa gói tin vào hàng đợi
            packet.sequence = self._seq_counter
            self._seq_counter += 1
            if self._is_priority:
                # Tie-breaking (HDH-88): gói tin mới chỉ chen trước gói tin có priority THẤP HƠN hẳn,
                # nên cùng priority thì gói tin vào trước luôn đứng trước (FIFO).
                index = len(self._queue)
                for i, existing in enumerate(self._queue):
                    if packet < existing:
                        index = i
                        break
                self._queue.insert(index, packet)
            else:
                self._queue.append(packet)

            # Báo hiệu cho một Consumer đang chờ
            self._not_empty.notify()

            return IPCResult(
                status=IPCStatus.SUCCESS.value,
                data=packet,
                success=True,
                detail=f"Đã gửi gói tin #{packet.id} (Priority={packet.priority}) vào hàng đợi.",
            )

    def consume(
        self,
        process_id: str = "Consumer",
        timeout: float | None = 0.0,
    ) -> IPCResult:
        """
        Lấy một thông điệp (MessagePacket) ra khỏi hàng đợi.

        Args:
            process_id: Định danh tiến trình nhận.
            timeout:
                - 0.0: Non-blocking (cho GUI/step-by-step). Nếu rỗng, trả về ngay "BLOCKED".
                - > 0.0: Chờ tối đa `timeout` giây, hết hạn thì trả về "TIMEOUT".
                - None: Blocking vô hạn (chờ cho tới khi có tin nhắn mới).

        Returns:
            IPCResult: Trạng thái SUCCESS (kèm gói tin lấy ra), BLOCKED hoặc TIMEOUT.
        """
        start_time = time.time()

        with self._not_empty:
            try:
                # 1. Chờ cho đến khi hàng đợi có tin nhắn
                while len(self._queue) == 0:
                    if timeout == 0.0:
                        return IPCResult(
                            status=IPCStatus.BLOCKED.value,
                            success=False,
                            detail="Hàng đợi tin nhắn rỗng, không có gói tin nào.",
                        )
                    if timeout is not None:
                        remaining = timeout - (time.time() - start_time)
                        if remaining <= 0:
                            return IPCResult(
                                status=IPCStatus.TIMEOUT.value,
                                success=False,
                                detail=f"Quá thời gian chờ đọc ({timeout}s) do hàng đợi rỗng.",
                            )
                        with self._state_lock:
                            self._blocked_consumers[process_id] = start_time
                        self._not_empty.wait(timeout=remaining)
                    else:
                        with self._state_lock:
                            self._blocked_consumers[process_id] = start_time
                        self._not_empty.wait()
            finally:
                # Dù thành công hay thất bại, tiến trình không còn bị chặn
                with self._state_lock:
                    self._blocked_consumers.pop(process_id, None)

            # 2. Rút gói tin ở đầu hàng đợi (gói tin ưu tiên cao nhất, vào sớm nhất)
            packet = self._queue.pop(0)

            # Báo hiệu cho một Producer đang chờ
            self._not_full.notify()

            return IPCResult(
                status=IPCStatus.SUCCESS.value,
                data=packet,
                success=True,
                detail=f"Đã lấy gói tin #{packet.id} ra khỏi hàng đợi.",
            )

    def get_state(self) -> dict[str, Any]:
        """
        Lấy snapshot toàn bộ trạng thái hiện tại của Message Queue để GUI render.

        Returns:
            dict gồm các khóa bắt buộc của IIPCMechanism: "buffer", "in_ptr", "out_ptr",
            "mutex", "empty", "full", "blocked_processes"; kèm các khóa bổ sung phục vụ
            hiển thị ("mechanism", "queue_type", "capacity", "count", "items").
        """
        # Thử khóa không chờ để biết mutex có đang bị tiến trình khác giữ hay không;
        # nếu đang bị giữ thì chờ rồi vẫn lấy snapshot nhất quán.
        mutex_free = self._mutex.acquire(blocking=False)
        if not mutex_free:
            self._mutex.acquire()
        try:
            current_queue = list(self._queue)
            with self._state_lock:
                blocked = list(self._blocked_producers.keys()) + list(self._blocked_consumers.keys())

            # Chuẩn hóa buffer thành mảng cố định kích thước capacity (ô trống là None)
            buffer_snapshot: list[Any | None] = [None] * self._capacity
            for i, pkt in enumerate(current_queue[:self._capacity]):
                buffer_snapshot[i] = pkt.to_dict()

            return {
                "mechanism": "MESSAGE_QUEUE",
                "queue_type": "PRIORITY" if self._is_priority else "FIFO",
                "capacity": self._capacity,
                "count": len(current_queue),
                "buffer": buffer_snapshot,
                "in_ptr": len(current_queue),
                "out_ptr": 0,
                "mutex": 1 if mutex_free else 0,
                "empty": max(0, self._capacity - len(current_queue)),
                "full": len(current_queue),
                "blocked_processes": blocked,
                "items": [pkt.to_dict() for pkt in current_queue],
            }
        finally:
            self._mutex.release()

    def reset(self) -> None:
        """Khôi phục trạng thái ban đầu của hàng đợi (xóa gói tin, đặt lại bộ đếm sequence)."""
        with self._mutex:
            self._queue.clear()
            self._seq_counter = 0
            with self._state_lock:
                self._blocked_producers.clear()
                self._blocked_consumers.clear()
            self._not_full.notify_all()
            self._not_empty.notify_all()

    # --- Các phương thức tương thích ngược (Backward-compatible Aliases) ---
    def enqueue(self, packet: MessagePacket, timeout: Optional[float] = None) -> bool:
        """Alias cho produce() tương thích với mã nguồn cũ."""
        res = self.produce(packet, process_id="Producer", timeout=timeout)
        return res.success

    def dequeue(self, timeout: Optional[float] = None) -> Optional[MessagePacket]:
        """Alias cho consume() tương thích với mã nguồn cũ."""
        res = self.consume(process_id="Consumer", timeout=timeout)
        return res.data if res.success else None

    def _normalize_packet(self, item: Any, process_id: str) -> MessagePacket:
        """Đóng gói item (MessagePacket, dict hoặc giá trị bất kỳ) thành MessagePacket."""
        if isinstance(item, MessagePacket):
            return item
        if isinstance(item, dict):
            return MessagePacket(
                id=item.get("id", int(time.time() * 1000) % 100000),
                sender=item.get("sender", process_id),
                receiver=item.get("receiver", "Receiver"),
                message=str(item.get("message", "")),
                delay_ms=int(item.get("delay_ms", 0)),
                priority=int(item.get("priority", 0)),
            )
        # Nếu item là chuỗi hoặc dữ liệu khác
        return MessagePacket(
            id=int(time.time() * 1000) % 100000,
            sender=process_id,
            receiver="Receiver",
            message=str(item),
        )


# Alias tương thích tên lớp cũ
MessageQueueCore = MessageQueue