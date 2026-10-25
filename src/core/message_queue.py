"""
Module: message_queue.py
Mô tả: Hiện thực cơ chế IPC Message Queue (Hàng đợi thông điệp).
       Tuân thủ hoàn toàn Interface IIPCMechanism (src/core/ipc_interface.py).
       Hỗ trợ cả cơ chế FIFO lẫn Priority Queue, an toàn đa luồng bằng Condition Variable (Monitor).
       Cung cấp API non-blocking (timeout=0.0) cho GUI và blocking/timeout cho Worker.
Tasks: HDH-14, HDH-15, HDH-27, HDH-28, HDH-29
Python version: 3.10+
"""

from __future__ import annotations

import heapq
import threading
import time
from dataclasses import dataclass
from typing import Any, Optional

from src.core.ipc_interface import IIPCMechanism, IPCResult, IPCStatus
from src.core import log_trace

@dataclass
class MessagePacket:
    """
    Cấu trúc khuôn mẫu của một gói tin (MessagePacket) theo đặc tả HDH-13.
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
            "payload_size_bytes": getattr(self, "payload_size_bytes", len(self.message.encode("utf-8"))),
        }

    def __lt__(self, other: Any) -> bool:
        """Hỗ trợ so sánh trong Priority Queue (độ ưu tiên cao hơn xếp trước, nếu bằng nhau so sánh timestamp)."""
        if not isinstance(other, MessagePacket):
            return NotImplemented
        if self.priority != other.priority:
            return self.priority > other.priority  # Priority số lớn hơn = ưu tiên cao hơn
        return self.timestamp < other.timestamp


class MessageQueue(IIPCMechanism):
    """
    Hiện thực lõi hàng đợi tin nhắn (Message Queue Core) kế thừa IIPCMechanism.

    Nguyên lý đồng bộ (Theo lý thuyết Hệ điều hành - Monitor Pattern):
    - `mutex`: Lock bảo vệ vùng Critical Section của hàng đợi tin nhắn.
    - `not_full`: Condition Variable báo hiệu khi hàng đợi có chỗ trống (được notify bởi Consumer).
    - `not_empty`: Condition Variable báo hiệu khi hàng đợi có tin nhắn mới (được notify bởi Producer).
    - Hỗ trợ chế độ FIFO thuần túy hoặc Priority Queue theo tham số `is_priority`.
    """

    def __init__(self, capacity: int, is_priority: bool = False) -> None:
        """
        Khởi tạo hàng đợi tin nhắn với dung lượng `capacity`.

        Args:
            capacity: Số gói tin tối đa hàng đợi có thể chứa (phải > 0).
            is_priority: True nếu kích hoạt chế độ hàng đợi ưu tiên (Priority Queue).
        """
        super().__init__(capacity)
        self._is_priority = is_priority
        self._queue: list[MessagePacket] = []

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
                - > 0.0: Chờ tối đa `timeout` giây trước khi trả về "BLOCKED".
                - None: Blocking vô hạn (chờ cho tới khi có chỗ trống).
        """
        packet = self._normalize_packet(item, process_id)
        start_time = time.time()

        with self._not_full:
            # 1. Kiểm tra hàng đợi đầy
            while len(self._queue) >= self._capacity:
                log_trace("WAIT_EMPTY", f"Process: {process_id}")
                if timeout == 0.0:
                    return IPCResult(
                        status=IPCStatus.BLOCKED.value,
                        success=False,
                        detail=f"Hàng đợi tin nhắn đã đầy ({len(self._queue)}/{self._capacity}).",
                    )
                if timeout is not None:
                    elapsed = time.time() - start_time
                    remaining = timeout - elapsed
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

            # Khi thoát vòng lặp chờ, giải phóng cờ blocked
            with self._state_lock:
                self._blocked_producers.pop(process_id, None)

            # 2. Đưa gói tin vào hàng đợi
            if self._is_priority:
                # Đưa vào danh sách có sắp xếp theo priority giảm dần
                inserted = False
                for i, existing in enumerate(self._queue):
                    if packet.priority > existing.priority:
                        self._queue.insert(i, packet)
                        inserted = True
                        break
                if not inserted:
                    self._queue.append(packet)
            else:
                self._queue.append(packet)

            # Báo hiệu cho các Consumer đang chờ
            self._not_empty.notify()
            log_trace("ENQUEUE", f"Packet_ID: {packet.id}")
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
                - > 0.0: Chờ tối đa `timeout` giây trước khi trả về "BLOCKED".
                - None: Blocking vô hạn (chờ cho tới khi có tin nhắn mới).
        """
        start_time = time.time()

        with self._not_empty:
            # 1. Kiểm tra hàng đợi rỗng
            while len(self._queue) == 0:
                log_trace("WAIT_FULL", f"Process: {process_id}")
                if timeout == 0.0:
                    return IPCResult(
                        status=IPCStatus.BLOCKED.value,
                        success=False,
                        detail="Hàng đợi tin nhắn rỗng, không có gói tin nào.",
                    )
                if timeout is not None:
                    elapsed = time.time() - start_time
                    remaining = timeout - elapsed
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

            # Khi thoát vòng lặp chờ, giải phóng cờ blocked
            with self._state_lock:
                self._blocked_consumers.pop(process_id, None)

            # 2. Rút gói tin ra khỏi hàng đợi
            packet = self._queue.pop(0)
            log_trace("DEQUEUE", f"Packet_ID: {packet.id}")
            # Báo hiệu cho các Producer đang chờ
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
        """
        with self._mutex:
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
                "mutex": 0 if self._mutex.locked() else 1,
                "empty": max(0, self._capacity - len(current_queue)),
                "full": len(current_queue),
                "blocked_processes": blocked,
                "items": [pkt.to_dict() for pkt in current_queue],
            }

    def reset(self) -> None:
        """Khôi phục trạng thái ban đầu của hàng đợi."""
        with self._mutex:
            self._queue.clear()
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
