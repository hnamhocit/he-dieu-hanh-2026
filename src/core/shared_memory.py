"""
Module: shared_memory.py
Mô tả: Hiện thực cơ chế IPC Shared Memory với kiến trúc Bounded Buffer (Mảng vòng).
       Sử dụng threading.Semaphore và threading.Lock để đồng bộ hóa hoàn toàn.
       Tách biệt khỏi GUI, hỗ trợ cả cơ chế Non-blocking (try_acquire) cho GUI ticker
       lẫn Blocking/Timeout cho Worker Threads mà không gây treo Main Thread.
Tasks: HDH-24, HDH-86, HDH-90
Python version: 3.10+
"""

from __future__ import annotations

import copy
import threading
import time
from typing import Any

from src.core import log_trace
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

    Đặc tính quan trọng phục vụ GUI & Multi-threading (HDH-86):
    - Khi Buffer Full hoặc Buffer Empty, nếu gọi với `timeout=0.0` (mặc định), hàm sẽ sử dụng
      `try_acquire` (non-blocking) và trả về ngay lập tức `status="BLOCKED"`.
      Tuyệt đối KHÔNG có vòng lặp `while True` bận (Busy-waiting) gây đông cứng giao diện.
    - Rollback Semaphore khi tranh chấp Mutex: nếu chiếm được counting semaphore nhưng
      không chiếm được mutex trong chế độ non-blocking/timeout, hàm sẽ tự động giải phóng (release)
      lại semaphore đó để tránh thất thoát tài nguyên (Semaphore Leak).
    - Cung cấp hàm `get_state()` trả về snapshot tức thời của bộ đệm và biến đồng bộ.
    - Cung cấp hàm `verify_invariants()` kiểm chứng tính bất biến toán học của hệ thống.
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

    def _extract_error_and_delay(self, item: Any) -> tuple[str, float]:
        """Trích xuất an toàn cấu hình mô phỏng lỗi (DELAY, CHECKSUM) từ item."""
        sim_error = "NONE"
        delay_sec = 0.0

        if isinstance(item, dict):
            sim_error = str(item.get("simulate_error", "NONE")).upper()
            raw_delay = item.get("delay_ms", 0)
            if isinstance(raw_delay, (int, float)) and raw_delay > 0:
                delay_sec = raw_delay / 1000.0
        elif hasattr(item, "simulate_error"):
            sim_error = str(getattr(item, "simulate_error", "NONE")).upper()
            raw_delay = getattr(item, "delay_ms", 0)
            if isinstance(raw_delay, (int, float)) and raw_delay > 0:
                delay_sec = raw_delay / 1000.0

        return sim_error, delay_sec

    def produce(
        self,
        item: Any,
        process_id: str = "Producer",
        timeout: float | None = 0.0,
        *,
        events: list[dict[str, Any]] | None = None,
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
            events: Danh sách tùy chọn để ghi lại các frame phục vụ GUI animation.

        Returns:
            IPCResult: Kết quả thao tác kèm trạng thái "SUCCESS" hoặc "BLOCKED".
        """
        # Tầng Guard bảo vệ biên cực đại: không cho phép payload vượt quá 100 ký tự (Kịch bản 7 Oracle)
        msg_str = ""
        if isinstance(item, str):
            msg_str = item
        elif hasattr(item, "message"):
            msg_str = str(item.message)
        elif isinstance(item, dict) and "message" in item:
            msg_str = str(item["message"])

        if len(msg_str) > 100:
            return IPCResult(
                status=IPCStatus.ERROR.value,
                data=None,
                success=False,
                detail=f"Payload vượt quá giới hạn 100 ký tự (độ dài: {len(msg_str)}). Bị chặn bởi tầng Guard.",
            )

        # Xử lý mô phỏng độ trễ (Fault Injection - DELAY) trước khi vào đoạn găng
        sim_error, delay_sec = self._extract_error_and_delay(item)
        if sim_error == "DELAY" or delay_sec > 0:
            actual_delay = delay_sec if delay_sec > 0 else 0.05
            time.sleep(actual_delay)

        # =====================================================================
        # GIAI ĐOẠN 1: WAIT(EMPTY) - Kiểm tra và chiếm dụng ô nhớ trống
        # =====================================================================
        is_blocking = (timeout is None) or (timeout > 0.0)
        start_wait_time = time.time()

        if not is_blocking:
            # Chế độ Non-blocking (Dành cho GUI ticker/step simulation)
            acquired_empty = self._empty.acquire(blocking=False)
            if not acquired_empty:
                log_trace("WAIT_EMPTY", f"Process: {process_id}")
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

            wait_kwargs: dict[str, Any] = {"blocking": True}
            if timeout is not None:
                wait_kwargs["timeout"] = timeout

            acquired_empty = self._empty.acquire(**wait_kwargs)

            if not acquired_empty:
                log_trace("WAIT_EMPTY", f"Process: {process_id} (Timeout)")
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
        mutex_acquired = False
        if not is_blocking:
            mutex_acquired = self._mutex.acquire(blocking=False)
        elif timeout is None:
            mutex_acquired = self._mutex.acquire(blocking=True)
        else:
            # Tính thời gian timeout còn lại cho Mutex sau khi đã chờ Semaphore
            elapsed = time.time() - start_wait_time
            remaining_timeout = max(0.0, timeout - elapsed)
            mutex_acquired = self._mutex.acquire(timeout=remaining_timeout)

        if not mutex_acquired:
            # ROLLBACK BẮT BUỘC: Hoàn trả lại Semaphore empty đã chiếm để tránh rò rỉ (Leak)
            self._empty.release()
            log_trace("MUTEX_BLOCKED", f"Process: {process_id}")
            with self._state_lock:
                self._blocked_producers[process_id] = time.time()
            return IPCResult(
                status=IPCStatus.BLOCKED.value,
                data=None,
                success=False,
                detail=f"[{process_id}] bị BLOCKED tại Mutex.",
            )

        try:
            with self._state_lock:
                self._mutex_holder = process_id

            # --- BẮT ĐẦU CRITICAL SECTION ---
            slot_index = self._in_ptr
            log_trace("LOCK_ACQUIRE", f"Process: {process_id}")
            self._record_event(events, "LOCKED", slot_index, process_id)

            self._record_event(events, "WRITING", slot_index, process_id)

            # Mô phỏng Fault Injector: CHECKSUM nếu được cấu hình
            stored_item = item
            if sim_error == "CHECKSUM":
                log_trace("FAULT_CHECKSUM", f"Process: {process_id}")
                if isinstance(stored_item, dict):
                    stored_item = dict(stored_item)
                    stored_item["checksum"] = "ERR_CHECKSUM_FAILED"
                    stored_item["is_corrupted"] = True

            self._buffer[slot_index] = stored_item
            log_trace("WRITE_SLOT", f"Slot: {slot_index}")

            self._in_ptr = (self._in_ptr + 1) % self._capacity
            self._count += 1
            self._step_counter += 1
            self._record_event(events, "WRITTEN", slot_index, process_id)
            # --- KẾT THÚC CRITICAL SECTION ---

        finally:
            # =================================================================
            # GIAI ĐOẠN 3: SIGNAL(MUTEX) - Rời khỏi Critical Section
            # =================================================================
            with self._state_lock:
                self._mutex_holder = None
            self._mutex.release()
            log_trace("LOCK_RELEASE", f"Process: {process_id}")

        # =====================================================================
        # GIAI ĐOẠN 4: SIGNAL(FULL) - Báo hiệu có dữ liệu cho Consumer
        # =====================================================================
        self._full.release()
        log_trace("SIGNAL_FULL", f"Count: {self._count}")

        # Dọn dẹp consumer blocked nếu buffer đã có dữ liệu
        with self._state_lock:
            if self._blocked_consumers and self._count > 0:
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
        *,
        events: list[dict[str, Any]] | None = None,
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
            events: Danh sách tùy chọn để ghi lại các frame phục vụ GUI animation.

        Returns:
            IPCResult: Kết quả thao tác chứa item hoặc trạng thái "BLOCKED".
        """
        # =====================================================================
        # GIAI ĐOẠN 1: WAIT(FULL) - Kiểm tra và chiếm dụng ô nhớ có dữ liệu
        # =====================================================================
        is_blocking = (timeout is None) or (timeout > 0.0)
        start_wait_time = time.time()

        if not is_blocking:
            # Chế độ Non-blocking (Dành cho GUI ticker/step simulation)
            acquired_full = self._full.acquire(blocking=False)
            if not acquired_full:
                log_trace("WAIT_FULL", f"Process: {process_id}")
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

            wait_kwargs: dict[str, Any] = {"blocking": True}
            if timeout is not None:
                wait_kwargs["timeout"] = timeout

            acquired_full = self._full.acquire(**wait_kwargs)

            if not acquired_full:
                log_trace("WAIT_FULL", f"Process: {process_id} (Timeout)")
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
        mutex_acquired = False
        if not is_blocking:
            mutex_acquired = self._mutex.acquire(blocking=False)
        elif timeout is None:
            mutex_acquired = self._mutex.acquire(blocking=True)
        else:
            elapsed = time.time() - start_wait_time
            remaining_timeout = max(0.0, timeout - elapsed)
            mutex_acquired = self._mutex.acquire(timeout=remaining_timeout)

        if not mutex_acquired:
            # ROLLBACK BẮT BUỘC: Hoàn trả lại Semaphore full đã chiếm
            self._full.release()
            log_trace("MUTEX_BLOCKED", f"Process: {process_id}")
            with self._state_lock:
                self._blocked_consumers[process_id] = time.time()
            return IPCResult(
                status=IPCStatus.BLOCKED.value,
                data=None,
                success=False,
                detail=f"[{process_id}] bị BLOCKED tại Mutex.",
            )

        try:
            with self._state_lock:
                self._mutex_holder = process_id

            # --- BẮT ĐẦU CRITICAL SECTION ---
            slot_index = self._out_ptr
            log_trace("LOCK_ACQUIRE", f"Process: {process_id}")
            self._record_event(events, "LOCKED", slot_index, process_id)
            self._record_event(events, "READING", slot_index, process_id)

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
            self._mutex.release()
            log_trace("LOCK_RELEASE", f"Process: {process_id}")

        # =====================================================================
        # GIAI ĐOẠN 4: SIGNAL(EMPTY) - Báo hiệu có thêm ô trống cho Producer
        # =====================================================================
        self._empty.release()
        log_trace("SIGNAL_EMPTY", f"Count: {self._count}")

        # Dọn dẹp producer blocked nếu buffer đã có chỗ trống
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

    def _record_event(
        self,
        events: list[dict[str, Any]] | None,
        phase: str,
        slot_index: int,
        process_id: str,
    ) -> None:
        """Thu thập snapshot trạng thái trong thao tác để phục vụ GUI frame animation."""
        if events is not None:
            events.append({
                "phase": phase,
                "slot_index": slot_index,
                "process_id": process_id,
                "snapshot": self.get_state(),
            })

    def get_state(self) -> dict[str, Any]:
        """
        Lấy snapshot trạng thái toàn diện của vùng nhớ chung để GUI vẽ Canvas/Graphics.

        Đảm bảo Thread-safe khi lấy dữ liệu mà không làm gián đoạn các luồng khác.
        Tạo bản sao độc lập của mảng đệm buffer để việc chỉnh sửa sau đó không làm ảnh hưởng
        đến các frame snapshot đã lưu trong lịch sử.

        Returns:
            dict bao gồm:
                - "buffer": Bản sao sâu/nông an toàn của mảng dữ liệu Circular Buffer.
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
            blocked_list = list(self._blocked_producers.keys()) + list(self._blocked_consumers.keys())
            mutex_val = 0 if self._mutex.locked() else 1
            empty_val = self._capacity - self._count
            full_val = self._count

            # Tạo bản sao shallow của buffer (nếu phần tử là dict thì copy dict để an toàn)
            buffer_copy = [
                dict(elem) if isinstance(elem, dict) else elem
                for elem in self._buffer
            ]

            return {
                "buffer": buffer_copy,
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

    def verify_invariants(self) -> tuple[bool, str]:
        """
        Kiểm chứng tính đúng đắn toán học (System Invariants) của vùng nhớ chia sẻ.

        Returns:
            (True, "OK") nếu mọi bất biến đều thỏa mãn, ngược lại trả về (False, mô_tả_lỗi).
        """
        with self._state_lock:
            if not (0 <= self._count <= self._capacity):
                return False, f"Vi phạm bất biến count: {self._count} ngoài [0, {self._capacity}]"
            if not (0 <= self._in_ptr < self._capacity):
                return False, f"Vi phạm bất biến in_ptr: {self._in_ptr} ngoài [0, {self._capacity - 1}]"
            if not (0 <= self._out_ptr < self._capacity):
                return False, f"Vi phạm bất biến out_ptr: {self._out_ptr} ngoài [0, {self._capacity - 1}]"

            actual_occupied = sum(1 for slot in self._buffer if slot is not None)
            if actual_occupied != self._count:
                return (
                    False,
                    f"Số ô chứa dữ liệu thực tế ({actual_occupied}) không khớp self._count ({self._count})",
                )

            return True, "Hệ thống bảo toàn tuyệt đối mọi bất biến đồng bộ."

    def reset(self) -> None:
        """
        Thiết lập lại toàn bộ trạng thái về ban đầu (Dùng cho nút Reset trên GUI hoặc Re-run test).
        """
        with self._state_lock:
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
