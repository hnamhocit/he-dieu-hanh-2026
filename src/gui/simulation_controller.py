"""Chạy CSV tuần tự và phát lại sự kiện Core bằng QTimer.

BLOCKED được ghi nhận rồi chuyển bước kế tiếp, không tự retry.
Không tạo OS process; animation không giữ mutex hoặc tính vào latency IPC.
"""

from collections import deque
from datetime import datetime
from time import perf_counter

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from src.core.message_queue import MessageQueue
from src.core.shared_memory import SharedMemory


class SimulationController(QObject):
    frame_changed = pyqtSignal(dict)
    step_completed = pyqtSignal(dict)
    trace_recorded = pyqtSignal(dict)
    finished = pyqtSignal(str)

    def __init__(self, parent=None, animation_ms=220):
        super().__init__(parent)
        self.animation_ms = animation_ms
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._advance)
        self.reset()

    def start(self, messages, configuration):
        if self.running:
            return
        self.reset()
        try:
            name = configuration["mechanism"]
            factories = {"SHARED_MEMORY": SharedMemory, "MESSAGE_QUEUE": MessageQueue}
            if name not in factories:
                raise ValueError("Pipe chưa được hỗ trợ trong bộ chạy này.")
            steps = [dict(step) for step in messages]
            if not steps:
                raise ValueError("Chưa có dữ liệu CSV.")
            for step in steps:
                if step["action"] not in {"PRODUCE", "CONSUME", "SEND", "RECEIVE"}:
                    raise ValueError(f"Action không hỗ trợ: {step['action']}")
                delay = step["delay_ms"]
                if not isinstance(delay, int) or not 0 <= delay <= 2_147_483_647:
                    raise ValueError(f"delay_ms của bước {step['id']} ngoài phạm vi QTimer.")
            is_priority = bool(configuration.get("is_priority", False))
            if name == "MESSAGE_QUEUE":
                self.core = MessageQueue(configuration["buffer_capacity"], is_priority=is_priority)
            else:
                self.core = factories[name](configuration["buffer_capacity"])
        except (KeyError, TypeError, ValueError) as error:
            self._finish(f"Không thể bắt đầu: {error}")
            return
        self.steps = steps
        self.mechanism_name = name
        self.running = True
        self._schedule_next()

    def _arm(self, callback, delay):
        self._callback = callback
        if self.running and not self.paused:
            self.timer.start(delay)

    def _advance(self):
        if self.running and not self.paused:
            self._callback()

    def _schedule_next(self):
        if not self.running or self.paused:
            return
        if self.index >= len(self.steps):
            self._finish("Đã chạy hết kịch bản.")
        else:
            self._arm(self._execute_step, self.steps[self.index]["delay_ms"])

    def _execute_step(self):
        step = self.steps[self.index]
        timestamp = datetime.now().astimezone().isoformat(sep=" ", timespec="milliseconds")
        started = perf_counter()
        events = []
        try:
            kwargs = {"process_id": step["sender"], "timeout": 0.0}
            if isinstance(self.core, SharedMemory):
                kwargs["events"] = events
            if step["action"] in ("PRODUCE", "SEND"):
                result = self.core.produce(dict(step), **kwargs)
            else:
                result = self.core.consume(**kwargs)
            snapshot = self.core.get_state()
        except Exception as error:
            self.trace_recorded.emit({
                "timestamp": timestamp, "step_id": step["id"],
                "process": step["sender"], "action": step["action"],
                "mechanism": self.mechanism_name, "status": "ERROR",
                "latency_ms": (perf_counter() - started) * 1000,
                "detail": str(error),
            })
            self._finish(f"Lỗi ở bước {step['id']}: {error}")
            return
        self._pending = {
            "step": dict(step), "result": result, "snapshot": snapshot,
            "completed": self.index + 1, "total": len(self.steps),
            "latency_ms": (perf_counter() - started) * 1000,
            "timestamp": timestamp,
        }
        self._frames = deque(events)
        self._play_next_frame()

    def _play_next_frame(self):
        if not self.running or self.paused:
            return
        if self._frames:
            frame = self._frames.popleft()
            frame["step"] = self._pending["step"]
            self._arm(self._play_next_frame, self.animation_ms)
            self.frame_changed.emit(frame)
            return
        event = self._pending
        generation = self._generation
        self._pending = None
        step, result = event["step"], event["result"]
        self.index += 1
        state = event["snapshot"]
        self.trace_recorded.emit({
            "timestamp": event["timestamp"], "step_id": step["id"],
            "process": step["sender"], "action": step["action"],
            "mechanism": self.mechanism_name, "status": result.status,
            "latency_ms": event["latency_ms"],
            "detail": (f"{result.detail} | buffer={state['buffer']} | "
                       f"Mutex={state['mutex']}, Empty={state['empty']}, Full={state['full']}"),
        })
        if not self.running or generation != self._generation:
            return
        self._callback = self._schedule_next
        self.remaining_delay = 0
        self.step_completed.emit(event)
        if self.running and generation == self._generation:
            self._schedule_next()

    def pause(self):
        if self.running and not self.paused:
            self.remaining_delay = max(0, self.timer.remainingTime())
            self.timer.stop()
            self.paused = True

    def resume(self):
        if self.running and self.paused:
            self.paused = False
            self.timer.start(self.remaining_delay)

    def reset(self):
        self._generation = getattr(self, "_generation", 0) + 1
        self.timer.stop()
        self.running = False
        self.paused = False
        self.steps = []
        self.index = 0
        self.core = None
        self.mechanism_name = ""
        self.remaining_delay = 0
        self._frames = deque()
        self._pending = None
        self._callback = self._schedule_next

    def _finish(self, message):
        self.timer.stop()
        self.running = False
        self.paused = False
        self._frames.clear()
        self._pending = None
        self.finished.emit(message)
