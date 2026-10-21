"""Chạy tuần tự CSV bằng QTimer và API IPC non-blocking.

Các bước đầy/rỗng trả về BLOCKED rồi chuyển sang bước kế tiếp, không tự retry.
Danh tính tiến trình lấy từ CSV; bộ chạy này không tạo thêm OS process.
"""

from datetime import datetime
from time import perf_counter

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from src.core.shared_memory import SharedMemory
from src.core.message_queue import MessageQueue


class SimulationController(QObject):
    step_completed = pyqtSignal(dict)
    trace_recorded = pyqtSignal(dict)
    finished = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._execute_step)

        self.steps = []
        self.index = 0
        self.mechanism = None
        self.mechanism_name = ""
        self.running = False
        self.paused = False
        self.remaining_delay = 0

    def start(self, messages, configuration):
        if self.running:
            return

        try:
            mechanism_name = configuration["mechanism"]
            capacity = configuration["buffer_capacity"]
            if mechanism_name == "SHARED_MEMORY":
                mechanism = SharedMemory(capacity)
            elif mechanism_name == "MESSAGE_QUEUE":
                mechanism = MessageQueue(capacity)
            else:
                raise ValueError("Cơ chế IPC này chưa được hỗ trợ.")
            steps = [dict(step) for step in messages]
            if not steps:
                raise ValueError("Chưa có kịch bản CSV hợp lệ để chạy.")
        except (KeyError, TypeError, ValueError) as error:
            self.finished.emit(f"Không thể bắt đầu: {error}")
            return

        self.mechanism = mechanism
        self.mechanism_name = mechanism_name
        self.steps = steps
        self.index = 0
        self.running = True
        self.paused = False

        self._schedule_next()

    def _schedule_next(self):
        if not self.running or self.paused:
            return

        if self.index >= len(self.steps):
            self._finish("Đã chạy hết kịch bản.")
            return

        try:
            self.timer.start(self.steps[self.index]["delay_ms"])
        except (KeyError, TypeError, OverflowError) as error:
            self._finish(f"Độ trễ của bước {self.index + 1} không hợp lệ: {error}")

    def _execute_step(self):
        if not self.running or self.paused:
            return

        step = self.steps[self.index]
        action = step["action"]
        started = perf_counter()

        try:
            if action in ("PRODUCE", "SEND"):
                result = self.mechanism.produce(
                    dict(step),
                    process_id=step["sender"],
                    timeout=0.0,
                )
            elif action in ("CONSUME", "RECEIVE"):
                result = self.mechanism.consume(
                    process_id=step["sender"],
                    timeout=0.0,
                )
            else:
                raise ValueError(f"Action không hỗ trợ: {action}")

            snapshot = self.mechanism.get_state()

        except Exception as error:
            self._record_trace(step, "ERROR", str(error), started)
            self._finish(f"Lỗi khi chạy bước {step['id']}: {error}")
            return

        self._record_trace(step, result.status, result.detail, started)
        self.index += 1

        self.step_completed.emit(
            {
                "step": dict(step),
                "result": result,
                "snapshot": snapshot,
                "completed": self.index,
                "total": len(self.steps),
            }
        )

        self._schedule_next()

    def _record_trace(self, step, status, detail, started):
        """Thời lượng xử lý IPC và snapshot, không tính delay_ms của kịch bản."""
        self.trace_recorded.emit(
            {
                "timestamp": datetime.now()
                .astimezone()
                .isoformat(sep=" ", timespec="milliseconds"),
                "step_id": step["id"],
                "process": step["sender"],
                "action": step["action"],
                "mechanism": self.mechanism_name,
                "status": status,
                "latency_ms": (perf_counter() - started) * 1000,
                "detail": detail,
            }
        )

    def pause(self):
        if not self.running or self.paused:
            return

        self.remaining_delay = max(0, self.timer.remainingTime())
        self.timer.stop()
        self.paused = True

    def resume(self):
        if not self.running or not self.paused:
            return

        self.paused = False
        self.timer.start(self.remaining_delay)

    def stop(self):
        if self.running:
            self._finish("Đã dừng mô phỏng.")

    def reset(self):
        self.stop()
        self.mechanism = None
        self.steps = []
        self.index = 0
        self.remaining_delay = 0

    def _finish(self, message):
        self.timer.stop()
        self.running = False
        self.paused = False
        self.finished.emit(message)
