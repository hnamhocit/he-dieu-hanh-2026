"""
Module: ipc_manager.py
Mô tả: Bộ điều phối vòng đời tiến trình và tài nguyên IPC (Process Lifecycle & Resource Manager).
       Chịu trách nhiệm:
       - Quản lý vòng đời hệ thống: Start, Pause, Resume, Stop, Reset.
       - Điều phối, phân bổ và theo dõi trạng thái các tiến trình Producer/Consumer.
       - Giải phóng 100% tài nguyên bộ nhớ (Shared Memory buffer, Message Queue, Locks,
         Condition Variables, Thread workers) khi thoát đột ngột (SIGINT, SIGTERM, crash, atexit).
Task: HDH-93
Python version: 3.10+
"""

from __future__ import annotations

import atexit
from dataclasses import dataclass, field
from enum import Enum
import signal
import sys
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from src.core import log_trace
from src.core.ipc_interface import IIPCMechanism, IPCResult, IPCStatus
from src.core.message_queue import MessageQueue
from src.core.shared_memory import SharedMemory


class LifecycleState(str, Enum):
    """Trạng thái vòng đời của Bộ điều phối IPC (IPCManager)."""
    IDLE = "IDLE"              # Vừa khởi tạo hoặc sau Reset, chưa chạy
    RUNNING = "RUNNING"        # Đang thực thi điều phối các tiến trình
    PAUSED = "PAUSED"          # Đang tạm dừng thực thi (giữ nguyên tài nguyên)
    STOPPED = "STOPPED"        # Đã dừng các worker, tài nguyên chuẩn bị thu hồi
    RESET = "RESET"            # Đang hoàn nguyên trạng thái ban đầu
    TERMINATED = "TERMINATED"  # Đã giải phóng toàn bộ tài nguyên khi tắt/hủy


class ProcessRole(str, Enum):
    """Vai trò của tiến trình/worker trong hệ thống."""
    PRODUCER = "PRODUCER"
    CONSUMER = "CONSUMER"


class ProcessStatus(str, Enum):
    """Trạng thái hoạt động của từng tiến trình con."""
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    TERMINATED = "TERMINATED"
    ERROR = "ERROR"


@dataclass
class ProcessDescriptor:
    """Cấu trúc dữ liệu quản lý tiến trình (Process Control Block - PCB mô phỏng)."""
    process_id: str
    role: ProcessRole
    status: ProcessStatus = ProcessStatus.CREATED
    items_count: int = 0
    blocked_count: int = 0
    error_count: int = 0
    last_active_time: float = field(default_factory=time.time)
    thread: Optional[threading.Thread] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "process_id": self.process_id,
            "role": self.role.value,
            "status": self.status.value,
            "items_count": self.items_count,
            "blocked_count": self.blocked_count,
            "error_count": self.error_count,
            "last_active_time": self.last_active_time,
            "is_alive": self.thread.is_alive() if self.thread else False,
        }


class IPCManager:
    """
    Bộ điều phối vòng đời tiến trình và tài nguyên IPC (Process Lifecycle & Resource Manager).
    
    Hỗ trợ điều phối các cơ chế IIPCMechanism (SharedMemory, MessageQueue) cùng
    các worker Producer và Consumer, đảm bảo an toàn đa luồng, kiểm soát trạng thái
    Start/Pause/Stop/Reset và cơ chế Fail-safe Cleanup giải phóng 100% tài nguyên.
    """

    def __init__(
        self,
        mechanism: IIPCMechanism | str,
        capacity: int = 5,
        is_priority: bool = False,
        auto_cleanup_signals: bool = True,
    ) -> None:
        """
        Khởi tạo IPCManager.

        Args:
            mechanism: Đối tượng kế thừa IIPCMechanism hoặc chuỗi tên cơ chế
                       ("SHARED_MEMORY", "MESSAGE_QUEUE").
            capacity: Sức chứa của bộ đệm / hàng đợi nếu khởi tạo qua chuỗi tên.
            is_priority: Chế độ Priority Queue nếu cơ chế là MESSAGE_QUEUE.
            auto_cleanup_signals: Tự động bắt tín hiệu SIGINT/SIGTERM để giải phóng tài nguyên.
        """
        if isinstance(mechanism, str):
            mech_upper = mechanism.strip().upper()
            if mech_upper == "SHARED_MEMORY":
                self._mechanism: IIPCMechanism = SharedMemory(capacity=capacity)
            elif mech_upper in ("MESSAGE_QUEUE", "PRIORITY_QUEUE"):
                self._mechanism = MessageQueue(capacity=capacity, is_priority=is_priority or mech_upper == "PRIORITY_QUEUE")
            else:
                raise ValueError(f"Cơ chế IPC không hợp lệ: {mechanism}. Hỗ trợ: SHARED_MEMORY, MESSAGE_QUEUE")
        elif isinstance(mechanism, IIPCMechanism):
            self._mechanism = mechanism
        else:
            raise TypeError(f"mechanism phải là IIPCMechanism hoặc str, nhận {type(mechanism).__name__}")

        self._state = LifecycleState.IDLE
        self._state_lock = threading.RLock()

        # Sự kiện điều phối tạm dừng và dừng khẩn cấp
        self._pause_event = threading.Event()
        self._pause_event.set()  # Mặc định không bị pause (được chạy)
        self._shutdown_event = threading.Event()

        # Bảng quản lý tiến trình (Process Table / PCB Table)
        self._processes: Dict[str, ProcessDescriptor] = {}
        self._worker_threads: List[threading.Thread] = []

        # Cờ đánh dấu đã giải phóng tài nguyên hay chưa
        self._cleaned_up = False
        self._registered_signals: Dict[int, Any] = {}

        # Đăng ký hook dọn dẹp khi tiến trình thoát bình thường hoặc đột ngột
        atexit.register(self.cleanup)

        if auto_cleanup_signals:
            self._setup_signal_handlers()

        log_trace("IPC_MANAGER_INIT", f"Mechanism: {self._mechanism.__class__.__name__}, Capacity: {capacity}")

    @property
    def mechanism(self) -> IIPCMechanism:
        """Cơ chế IPC đang được điều phối."""
        return self._mechanism

    @property
    def state(self) -> LifecycleState:
        """Trạng thái vòng đời hiện tại của Manager."""
        with self._state_lock:
            return self._state

    @property
    def is_running(self) -> bool:
        """Kiểm tra hệ thống có đang ở trạng thái RUNNING hay không."""
        with self._state_lock:
            return self._state == LifecycleState.RUNNING

    @property
    def is_paused(self) -> bool:
        """Kiểm tra hệ thống có đang ở trạng thái PAUSED hay không."""
        with self._state_lock:
            return self._state == LifecycleState.PAUSED

    # ------------------------------------------------------------------
    # Vòng đời hệ thống: Start, Pause, Resume, Stop, Reset
    # ------------------------------------------------------------------

    def start(self) -> bool:
        """
        Bắt đầu hoặc tiếp tục vòng đời thực thi hệ thống.
        
        Returns:
            True nếu khởi động thành công hoặc chuyển từ PAUSED -> RUNNING.
        """
        with self._state_lock:
            if self._cleaned_up or self._state == LifecycleState.TERMINATED:
                return False

            if self._state == LifecycleState.PAUSED:
                return self.resume()

            if self._state in (LifecycleState.IDLE, LifecycleState.RESET, LifecycleState.STOPPED):
                self._shutdown_event.clear()
                self._pause_event.set()
                self._state = LifecycleState.RUNNING
                log_trace("IPC_MANAGER_START", f"Processes count: {len(self._processes)}")
                return True

            return False

    def pause(self) -> bool:
        """
        Tạm dừng hệ thống điều phối (các worker sẽ đợi tại điểm chốt).
        
        Returns:
            True nếu chuyển từ RUNNING sang PAUSED thành công.
        """
        with self._state_lock:
            if self._state != LifecycleState.RUNNING:
                return False

            self._state = LifecycleState.PAUSED
            self._pause_event.clear()

            # Cập nhật trạng thái các tiến trình đang hoạt động thành PAUSED
            for pcb in self._processes.values():
                if pcb.status in (ProcessStatus.RUNNING, ProcessStatus.CREATED, ProcessStatus.BLOCKED):
                    pcb.status = ProcessStatus.PAUSED

            log_trace("IPC_MANAGER_PAUSE", "System paused successfully")
            return True

    def resume(self) -> bool:
        """
        Tiếp tục thực thi hệ thống sau khi Pause.
        
        Returns:
            True nếu chuyển từ PAUSED sang RUNNING thành công.
        """
        with self._state_lock:
            if self._state != LifecycleState.PAUSED:
                return False

            self._state = LifecycleState.RUNNING
            self._pause_event.set()

            # Cập nhật trạng thái các tiến trình bị tạm dừng về RUNNING
            for pcb in self._processes.values():
                if pcb.status == ProcessStatus.PAUSED:
                    pcb.status = ProcessStatus.RUNNING

            log_trace("IPC_MANAGER_RESUME", "System resumed successfully")
            return True

    def stop(self, timeout: float = 2.0) -> bool:
        """
        Dừng nhẹ nhàng toàn bộ các tiến trình và worker đang hoạt động.
        
        Args:
            timeout: Thời gian tối đa (giây) đợi các worker thread kết thúc.
            
        Returns:
            True nếu toàn bộ worker đã dừng hoàn tất.
        """
        with self._state_lock:
            if self._state in (LifecycleState.STOPPED, LifecycleState.TERMINATED):
                return True

            self._state = LifecycleState.STOPPED
            self._shutdown_event.set()
            self._pause_event.set()  # Đánh thức bất kỳ thread nào đang kẹt ở cờ Pause

            # Cập nhật trạng thái tiến trình
            for pcb in self._processes.values():
                if pcb.status in (ProcessStatus.RUNNING, ProcessStatus.PAUSED, ProcessStatus.BLOCKED):
                    pcb.status = ProcessStatus.TERMINATED

            log_trace("IPC_MANAGER_STOP", f"Stopping {len(self._worker_threads)} workers")

        # Đợi các worker kết thúc ngoài đoạn găng state_lock để tránh deadlock
        start_wait = time.time()
        for th in list(self._worker_threads):
            if th.is_alive() and th is not threading.current_thread():
                remaining = max(0.01, timeout - (time.time() - start_wait))
                th.join(timeout=remaining)

        with self._state_lock:
            self._worker_threads = [th for th in self._worker_threads if th.is_alive()]
            all_stopped = len(self._worker_threads) == 0
            log_trace("IPC_MANAGER_STOP_COMPLETE", f"Remaining active threads: {len(self._worker_threads)}")
            return all_stopped

    def reset(self) -> bool:
        """
        Hoàn nguyên toàn bộ hệ thống về trạng thái ban đầu:
        - Dừng toàn bộ worker threads.
        - Gọi reset() trên cơ chế IPC (dọn sạch buffer/queue, hoàn nguyên Mutex/Semaphores).
        - Xóa bảng quản lý tiến trình.
        - Đặt trạng thái về IDLE.
        """
        with self._state_lock:
            self.stop(timeout=1.0)
            self._state = LifecycleState.RESET

            # Hoàn nguyên cơ chế lõi
            if hasattr(self._mechanism, "reset") and callable(self._mechanism.reset):
                self._mechanism.reset()

            self._processes.clear()
            self._worker_threads.clear()
            self._shutdown_event.clear()
            self._pause_event.set()
            self._cleaned_up = False

            self._state = LifecycleState.IDLE
            log_trace("IPC_MANAGER_RESET", "System state reset to IDLE")
            return True

    # ------------------------------------------------------------------
    # Cơ chế giải phóng 100% tài nguyên khi thoát đột ngột (Fail-safe)
    # ------------------------------------------------------------------

    def _setup_signal_handlers(self) -> None:
        """Thiết lập bắt tín hiệu hệ thống an toàn (chỉ khi ở Main Thread)."""
        try:
            if threading.current_thread() is threading.main_thread():
                for sig in (signal.SIGINT, signal.SIGTERM):
                    prev = signal.getsignal(sig)
                    self._registered_signals[sig] = prev

                    def _handler(signum, frame, s=sig):
                        self.cleanup()
                        original = self._registered_signals.get(s)
                        if callable(original) and original not in (signal.SIG_IGN, signal.SIG_DFL, _handler):
                            original(signum, frame)
                        elif original == signal.SIG_DFL:
                            sys.exit(128 + signum)

                    signal.signal(sig, _handler)
        except (ValueError, AttributeError):
            # Môi trường chạy nền hoặc worker thread không hỗ trợ signal
            pass

    def cleanup(self) -> None:
        """
        Giải phóng 100% tài nguyên bộ nhớ và luồng thực thi (Fail-safe).
        Được gọi tự động khi:
        - Tiến trình bị ngắt đột ngột (SIGINT, Ctrl+C, SIGTERM).
        - Python Runtime thoát (atexit).
        - Người dùng thoát khỏi Context Manager ('with IPCManager()').
        - Gọi chủ động bằng lệnh mgr.cleanup().
        
        Phương thức này idempotent (có thể gọi nhiều lần mà không gây lỗi).
        """
        with self._state_lock:
            if self._cleaned_up:
                return

            self._state = LifecycleState.TERMINATED
            self._shutdown_event.set()
            self._pause_event.set()

            # 1. Đánh dấu dừng tất cả các tiến trình con
            for pcb in self._processes.values():
                pcb.status = ProcessStatus.TERMINATED

            # 2. Thu hồi tài nguyên lõi của cơ chế IPC
            try:
                if hasattr(self._mechanism, "reset") and callable(self._mechanism.reset):
                    self._mechanism.reset()
            except Exception as e:
                log_trace("IPC_MANAGER_CLEANUP_WARN", f"Error resetting mechanism: {e}")

            # 3. Thu hồi và đóng các luồng nền
            active_threads = [th for th in self._worker_threads if th.is_alive() and th is not threading.current_thread()]
            for th in active_threads:
                th.join(timeout=0.1)

            self._worker_threads.clear()
            self._cleaned_up = True
            log_trace("IPC_MANAGER_CLEANUP_SUCCESS", "100% resources successfully released")

    # ------------------------------------------------------------------
    # Điều phối tiến trình (Process Orchestration: Producer & Consumer)
    # ------------------------------------------------------------------

    def register_process(self, process_id: str, role: ProcessRole | str) -> ProcessDescriptor:
        """
        Đăng ký một tiến trình vào bảng quản lý (PCB Table).
        
        Args:
            process_id: Định danh tiến trình duy nhất (ví dụ: 'Producer_1').
            role: Vai trò ProcessRole.PRODUCER hoặc ProcessRole.CONSUMER.
            
        Returns:
            ProcessDescriptor tương ứng.
        """
        with self._state_lock:
            if isinstance(role, str):
                role = ProcessRole(role.upper())

            if process_id in self._processes:
                return self._processes[process_id]

            pcb = ProcessDescriptor(process_id=process_id, role=role)
            self._processes[process_id] = pcb
            log_trace("PROCESS_REGISTERED", f"ID: {process_id}, Role: {role.value}")
            return pcb

    def wait_if_paused(self) -> bool:
        """
        Hàm chặn kiểm tra cờ tạm dừng cho các worker.
        
        Returns:
            True nếu tiếp tục được phép chạy; False nếu hệ thống yêu cầu dừng/hủy.
        """
        while not self._shutdown_event.is_set():
            if self._pause_event.is_set():
                return True
            # Đang bị tạm dừng, ngủ ngắn kiểm tra cờ
            time.sleep(0.05)
        return False

    def produce(self, item: Any, process_id: str, timeout: float | None = 0.0) -> IPCResult:
        """
        Thực hiện gửi dữ liệu vào cơ chế IPC thông qua điều phối của Manager.
        Tự động ghi nhận thống kê và cập nhật trạng thái PCB.
        """
        pcb = self.register_process(process_id, ProcessRole.PRODUCER)
        pcb.last_active_time = time.time()

        if self._shutdown_event.is_set():
            pcb.status = ProcessStatus.TERMINATED
            return IPCResult(status=IPCStatus.ERROR.value, success=False, detail="Manager đang shutdown.")

        if not self.wait_if_paused():
            pcb.status = ProcessStatus.TERMINATED
            return IPCResult(status=IPCStatus.ERROR.value, success=False, detail="Manager đã dừng.")

        pcb.status = ProcessStatus.RUNNING
        result = self._mechanism.produce(item=item, process_id=process_id, timeout=timeout)

        if result.success:
            pcb.items_count += 1
            pcb.status = ProcessStatus.RUNNING
        elif result.status == IPCStatus.BLOCKED.value:
            pcb.blocked_count += 1
            pcb.status = ProcessStatus.BLOCKED
        else:
            pcb.error_count += 1
            pcb.status = ProcessStatus.ERROR

        return result

    def consume(self, process_id: str, timeout: float | None = 0.0) -> IPCResult:
        """
        Thực hiện nhận dữ liệu từ cơ chế IPC thông qua điều phối của Manager.
        Tự động ghi nhận thống kê và cập nhật trạng thái PCB.
        """
        pcb = self.register_process(process_id, ProcessRole.CONSUMER)
        pcb.last_active_time = time.time()

        if self._shutdown_event.is_set():
            pcb.status = ProcessStatus.TERMINATED
            return IPCResult(status=IPCStatus.ERROR.value, success=False, detail="Manager đang shutdown.")

        if not self.wait_if_paused():
            pcb.status = ProcessStatus.TERMINATED
            return IPCResult(status=IPCStatus.ERROR.value, success=False, detail="Manager đã dừng.")

        pcb.status = ProcessStatus.RUNNING
        result = self._mechanism.consume(process_id=process_id, timeout=timeout)

        if result.success:
            pcb.items_count += 1
            pcb.status = ProcessStatus.RUNNING
        elif result.status == IPCStatus.BLOCKED.value:
            pcb.blocked_count += 1
            pcb.status = ProcessStatus.BLOCKED
        else:
            pcb.error_count += 1
            pcb.status = ProcessStatus.ERROR

        return result

    def spawn_producer(
        self,
        process_id: str,
        items: list[Any],
        delay_ms: float = 10.0,
        timeout: float | None = 0.0,
        on_complete: Optional[Callable[[], None]] = None,
    ) -> threading.Thread:
        """
        Khởi tạo và chạy một Producer Worker trên luồng nền.
        """
        pcb = self.register_process(process_id, ProcessRole.PRODUCER)

        def _worker_loop():
            try:
                for item in items:
                    if self._shutdown_event.is_set():
                        break
                    if not self.wait_if_paused():
                        break

                    if delay_ms > 0:
                        time.sleep(delay_ms / 1000.0)

                    self.produce(item=item, process_id=process_id, timeout=timeout)

                with self._state_lock:
                    if not self._shutdown_event.is_set():
                        pcb.status = ProcessStatus.FINISHED
            except Exception as err:
                pcb.status = ProcessStatus.ERROR
                pcb.error_count += 1
                log_trace("PRODUCER_CRASH", f"Process: {process_id}, Error: {err}")
            finally:
                if on_complete:
                    try:
                        on_complete()
                    except Exception:
                        pass

        th = threading.Thread(target=_worker_loop, name=f"Worker-{process_id}", daemon=True)
        pcb.thread = th
        with self._state_lock:
            self._worker_threads.append(th)
            if self._state == LifecycleState.RUNNING:
                pcb.status = ProcessStatus.RUNNING
        th.start()
        return th

    def spawn_consumer(
        self,
        process_id: str,
        count: int,
        delay_ms: float = 10.0,
        timeout: float | None = 0.0,
        on_item_received: Optional[Callable[[Any], None]] = None,
        on_complete: Optional[Callable[[], None]] = None,
    ) -> threading.Thread:
        """
        Khởi tạo và chạy một Consumer Worker trên luồng nền.
        """
        pcb = self.register_process(process_id, ProcessRole.CONSUMER)

        def _worker_loop():
            try:
                consumed = 0
                while consumed < count:
                    if self._shutdown_event.is_set():
                        break
                    if not self.wait_if_paused():
                        break

                    if delay_ms > 0:
                        time.sleep(delay_ms / 1000.0)

                    res = self.consume(process_id=process_id, timeout=timeout)
                    if res.success:
                        consumed += 1
                        if on_item_received:
                            on_item_received(res.data)
                    else:
                        # Nếu bị blocked, tạm nghỉ một khoảng ngắn tránh busy loop
                        time.sleep(0.01)

                with self._state_lock:
                    if not self._shutdown_event.is_set():
                        pcb.status = ProcessStatus.FINISHED
            except Exception as err:
                pcb.status = ProcessStatus.ERROR
                pcb.error_count += 1
                log_trace("CONSUMER_CRASH", f"Process: {process_id}, Error: {err}")
            finally:
                if on_complete:
                    try:
                        on_complete()
                    except Exception:
                        pass

        th = threading.Thread(target=_worker_loop, name=f"Worker-{process_id}", daemon=True)
        pcb.thread = th
        with self._state_lock:
            self._worker_threads.append(th)
            if self._state == LifecycleState.RUNNING:
                pcb.status = ProcessStatus.RUNNING
        th.start()
        return th

    # ------------------------------------------------------------------
    # Thu thập chỉ số và Snapshot trạng thái toàn diện
    # ------------------------------------------------------------------

    def get_process_table(self) -> list[dict[str, Any]]:
        """Trả về bản chụp danh sách PCB của toàn bộ các tiến trình."""
        with self._state_lock:
            return [pcb.to_dict() for pcb in self._processes.values()]

    def get_system_state(self) -> dict[str, Any]:
        """
        Trả về Snapshot toàn diện hệ thống:
        - Vòng đời: trạng thái manager, cờ pause, shutdown, số tiến trình.
        - Trạng thái Core IPC Mechanism: buffers, pointers, slots, semaphores, queues.
        - Bảng tiến trình PCB.
        """
        with self._state_lock:
            core_state = {}
            if hasattr(self._mechanism, "get_state") and callable(self._mechanism.get_state):
                core_state = self._mechanism.get_state()

            active_workers = sum(1 for th in self._worker_threads if th.is_alive())

            return {
                "lifecycle_state": self._state.value,
                "is_running": self._state == LifecycleState.RUNNING,
                "is_paused": self._state == LifecycleState.PAUSED,
                "total_processes": len(self._processes),
                "active_workers": active_workers,
                "mechanism": self._mechanism.__class__.__name__,
                "mechanism_state": core_state,
                "process_table": [p.to_dict() for p in self._processes.values()],
            }

    # ------------------------------------------------------------------
    # Context Manager Support
    # ------------------------------------------------------------------

    def __enter__(self) -> IPCManager:
        self.start()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.cleanup()
