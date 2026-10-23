"""Kiểm tra trình tự IPC, animation, pause/reset và lỗi tại ranh giới bước."""

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QElapsedTimer
    from PyQt6.QtTest import QSignalSpy, QTest
    from PyQt6.QtWidgets import QApplication
    from src.gui.simulation_controller import SimulationController
    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False


def step(number, action, delay=0):
    return {"id": number, "action": action,
            "sender": "P1" if action in ("PRODUCE", "SEND") else "C1",
            "receiver": "C1" if action in ("PRODUCE", "SEND") else "P1",
            "message": f"M{number}" if action in ("PRODUCE", "SEND") else "",
            "delay_ms": delay, "priority": 0}


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

    def wait_until(self, predicate):
        elapsed = QElapsedTimer()
        elapsed.start()
        while not predicate() and elapsed.elapsed() < 3000:
            QTest.qWait(5)
        self.assertTrue(predicate(), "Timed out waiting for controller")

    def start(self, steps, mechanism="SHARED_MEMORY", capacity=2):
        self.controller.start(steps, {"mechanism": mechanism, "buffer_capacity": capacity})

    def test_full_empty_and_wraparound_match_oracle(self):
        actions = ["PRODUCE", "PRODUCE", "PRODUCE", "CONSUME", "CONSUME", "CONSUME", "PRODUCE"]
        self.start([step(i, action) for i, action in enumerate(actions, 1)])
        self.wait_until(lambda: not self.controller.running)
        self.assertEqual([row[0]["snapshot"]["count"] for row in self.completed], [1, 2, 2, 1, 0, 0, 1])
        self.assertEqual([row[0]["status"] for row in self.traces],
                         ["SUCCESS", "SUCCESS", "BLOCKED", "SUCCESS", "SUCCESS", "BLOCKED", "SUCCESS"])
        self.assertEqual(len(self.frames), 10)
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
                         ["LOCKED", "WRITTEN", "LOCKED", "READING"])
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


if __name__ == "__main__":
    unittest.main()
