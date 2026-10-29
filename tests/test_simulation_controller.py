"""Kiểm tra trình tự IPC, animation, pause/reset và lỗi tại ranh giới bước."""

import os
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QElapsedTimer, QThreadPool, QTimer
    from PyQt6.QtTest import QSignalSpy, QTest
    from PyQt6.QtWidgets import QApplication
    from src.gui.simulation_controller import SimulationController
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False


def step(number, action, delay=0, priority=0):
    return {"id": number, "action": action,
            "sender": "P1" if action in ("PRODUCE", "SEND") else "C1",
            "receiver": "C1" if action in ("PRODUCE", "SEND") else "P1",
            "message": f"M{number}" if action in ("PRODUCE", "SEND") else "",
            "delay_ms": delay, "priority": priority}


@unittest.skipUnless(HAS_PYQT6, "PyQt6 is required for GUI tests")
class TestSimulationController(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.controller = SimulationController(animation_ms=0)
        self.completed = QSignalSpy(self.controller.step_completed)
        self.frames = QSignalSpy(self.controller.frame_changed)
        self.traces = QSignalSpy(self.controller.trace_recorded)
        self.finished = QSignalSpy(self.controller.finished)

    def tearDown(self):
        self.controller.reset()
        QThreadPool.globalInstance().waitForDone(5000)
        self.app.processEvents()

    def wait_until(self, predicate):
        elapsed = QElapsedTimer()
        elapsed.start()
        while not predicate() and elapsed.elapsed() < 3000:
            QTest.qWait(5)
        self.assertTrue(predicate(), "Timed out waiting for controller")

    def start(self, steps, mechanism="SHARED_MEMORY", capacity=2):
        self.controller.start(steps, {"mechanism": mechanism, "buffer_capacity": capacity})

    def test_start_message_queue_with_priority_mode(self):
        steps = [step(1, "SEND", priority=2), step(2, "SEND", priority=5)]
        self.controller.start(steps, {
            "mechanism": "MESSAGE_QUEUE",
            "buffer_capacity": 5,
            "is_priority": True,
        })
        self.wait_until(lambda: not self.controller.running)
        self.assertTrue(self.controller.core.is_priority)
        self.assertEqual(self.controller.core.count, 2)

    def test_full_empty_and_wraparound_match_oracle(self):
        actions = ["PRODUCE", "PRODUCE", "PRODUCE", "CONSUME", "CONSUME", "CONSUME", "PRODUCE"]
        self.start([step(i, action) for i, action in enumerate(actions, 1)])
        self.wait_until(lambda: not self.controller.running)
        self.assertEqual([row[0]["snapshot"]["count"] for row in self.completed], [1, 2, 2, 1, 0, 0, 1])
        self.assertEqual([row[0]["status"] for row in self.traces],
                         ["SUCCESS", "SUCCESS", "BLOCKED", "SUCCESS", "SUCCESS", "BLOCKED", "SUCCESS"])
        self.assertEqual(len(self.frames), 13)
        self.assertEqual(len(self.traces), 7)
        self.assertEqual(self.controller.core.get_state()["buffer"][0]["id"], 7)

    def test_pause_during_animation_preserves_current_frame(self):
        self.controller.animation_ms = 60
        self.start([step(1, "PRODUCE"), step(2, "CONSUME")])
        self.wait_until(lambda: len(self.frames) == 1)
        self.controller.pause()
        QTest.qWait(150)
        self.assertEqual(len(self.frames), 1)
        self.assertEqual(len(self.completed), 0)
        self.controller.resume()
        self.wait_until(lambda: not self.controller.running)
        self.assertEqual([row[0]["phase"] for row in self.frames],
                         ["LOCKED", "WRITING", "WRITTEN", "LOCKED", "READING"])
        self.assertEqual(len(self.traces), 2)

    def test_reset_mid_animation_cancels_old_frames_and_allows_restart(self):
        self.controller.animation_ms = 60
        self.start([step(1, "PRODUCE")])
        self.wait_until(lambda: len(self.frames) == 1)
        self.controller.reset()
        QTest.qWait(150)
        self.assertEqual(len(self.frames), 1)
        self.assertEqual(len(self.traces), 0)
        self.assertIsNone(self.controller.core)
        self.controller.animation_ms = 0
        self.start([step(2, "PRODUCE")])
        self.wait_until(lambda: not self.controller.running)
        self.assertEqual([row[0]["step"]["id"] for row in self.completed], [2])

    def test_pause_during_csv_delay_does_not_execute_early(self):
        self.start([step(1, "PRODUCE", 60)])
        self.controller.pause()
        QTest.qWait(100)
        self.assertEqual(self.controller.core.count, 0)
        self.controller.resume()
        self.wait_until(lambda: not self.controller.running)
        self.assertEqual(len(self.completed), 1)

    def test_zero_delay_still_yields_to_event_loop(self):
        self.start([step(i, "PRODUCE") for i in range(1, 100)], capacity=100)
        self.assertEqual(len(self.completed), 0)
        self.wait_until(lambda: not self.controller.running)
        self.assertEqual(len(self.completed), 99)

    def test_message_queue_uses_same_csv_contract(self):
        self.start([step(1, "SEND"), step(2, "RECEIVE")], "MESSAGE_QUEUE")
        self.wait_until(lambda: not self.controller.running)
        self.assertEqual(len(self.traces), 2)
        self.assertEqual(self.completed[-1][0]["result"].data.message, "M1")
        self.assertEqual(self.controller.core.get_state()["count"], 0)

    def test_unsupported_mechanism_and_timer_overflow_finish_cleanly(self):
        self.start([step(1, "PRODUCE")], "PIPE")
        self.assertFalse(self.controller.running)
        self.assertIn("Pipe", self.finished[-1][0])
        self.start([step(1, "PRODUCE", 2**31)])
        self.assertFalse(self.controller.running)
        self.assertIn("delay_ms", self.finished[-1][0])

    def test_core_exception_records_error_and_stops_timer(self):
        with patch("src.gui.simulation_controller.SharedMemory.produce", side_effect=RuntimeError("test error")):
            self.start([step(1, "PRODUCE")])
            self.wait_until(lambda: not self.controller.running)
        self.assertEqual(self.traces[0][0]["status"], "ERROR")
        self.assertFalse(self.controller.timer.isActive())
        self.assertEqual(len(self.completed), 0)

    def test_reset_from_trace_receiver_does_not_emit_stale_step(self):
        self.controller.trace_recorded.connect(lambda event: self.controller.reset())
        self.start([step(1, "PRODUCE")])
        self.wait_until(lambda: not self.controller.running)
        self.assertEqual(len(self.completed), 0)

    def test_mutex_is_released_before_animation_is_shown(self):
        self.controller.animation_ms = 60
        self.start([step(1, "PRODUCE")])
        self.wait_until(lambda: len(self.frames) == 1)
        self.assertEqual(self.frames[0][0]["snapshot"]["mutex"], 0)
        self.assertEqual(self.controller.core.get_state()["mutex"], 1)

    def test_csv_delay_is_not_applied_again_inside_core(self):
        from src.core.shared_memory import SharedMemory
        produce = SharedMemory.produce
        delays = []

        def record_delay(core, item, **kwargs):
            delays.append(item["delay_ms"])
            return produce(core, item, **kwargs)

        with patch.object(SharedMemory, "produce", record_delay):
            self.start([step(1, "PRODUCE", 20)])
            self.wait_until(lambda: not self.controller.running)
        self.assertEqual(delays, [0])
        self.assertEqual(self.completed[0][0]["step"]["delay_ms"], 20)

    def test_slow_core_keeps_ui_responsive_and_pause_defers_playback(self):
        from src.core.shared_memory import SharedMemory
        produce = SharedMemory.produce
        entered, release = threading.Event(), threading.Event()
        threads = []

        def slow_produce(core, *args, **kwargs):
            threads.append(threading.get_ident())
            entered.set()
            release.wait(3)
            return produce(core, *args, **kwargs)

        with patch.object(SharedMemory, "produce", slow_produce):
            try:
                self.start([step(1, "PRODUCE")])
                self.wait_until(entered.is_set)
                ticks = []
                QTimer.singleShot(0, lambda: ticks.append(True))
                self.wait_until(lambda: bool(ticks))
                self.assertNotEqual(threads[0], threading.get_ident())
                self.controller.pause()
                release.set()
                self.wait_until(lambda: self.controller._pending is not None)
                self.assertEqual(len(self.frames), 0)
                self.assertEqual(len(self.traces), 0)
                self.controller.resume()
                self.wait_until(lambda: not self.controller.running)
                self.assertEqual(len(threads), 1)
                self.assertEqual(len(self.completed), 1)
            finally:
                release.set()

    def test_reset_discards_in_flight_result_after_restart(self):
        from src.core.shared_memory import SharedMemory
        produce = SharedMemory.produce
        entered, release = threading.Event(), threading.Event()

        def slow_first(core, item, **kwargs):
            if item["id"] == 1:
                entered.set()
                release.wait(3)
            return produce(core, item, **kwargs)

        with patch.object(SharedMemory, "produce", slow_first):
            try:
                self.start([step(1, "PRODUCE")])
                self.wait_until(entered.is_set)
                self.controller.reset()
                self.start([step(2, "PRODUCE")])
                self.wait_until(lambda: not self.controller.running)
                release.set()
                self.wait_until(lambda: not self.controller._workers)
                self.assertEqual([row[0]["step"]["id"] for row in self.completed], [2])
                self.assertEqual(len(self.traces), 1)
                self.assertEqual(self.controller.core.get_state()["buffer"][0]["id"], 2)
            finally:
                release.set()


if __name__ == "__main__":
    unittest.main()
