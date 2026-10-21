"""Kiểm thử nạp CSV, điều khiển và xuất trace trên Qt offscreen."""

import csv
from datetime import datetime
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import QElapsedTimer, QEvent, QThreadPool, QTimer, Qt
    from PyQt6.QtGui import QFont, QFontDatabase
    from PyQt6.QtTest import QSignalSpy, QTest
    from PyQt6.QtWidgets import QApplication
    from src.gui.main_window import MainWindow, UIState

    HAS_PYQT6 = True
except ImportError:
    HAS_PYQT6 = False

from src.utils.csv_parser import CSVParser


SAMPLE = Path(__file__).resolve().parents[1] / "data/input/sample_messages.csv"
SAMPLE_COUNT = len(CSVParser().parse(SAMPLE))


@unittest.skipUnless(HAS_PYQT6, "PyQt6 is required for GUI tests")
class TestMainWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        # Qt offscreen trên Windows có thể không tự tìm được font hệ thống.
        if not QFontDatabase.families():
            fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
            for filename in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
                path = fonts / filename
                if path.is_file():
                    QFontDatabase.addApplicationFont(str(path))
        cls.app.setFont(QFont("Segoe UI", 10))

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.window = MainWindow()

    def tearDown(self):
        QThreadPool.globalInstance().waitForDone(5000)
        self.app.processEvents()
        self.window.close()
        self.window.deleteLater()
        self.app.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def wait_for_validation(self):
        timer = QElapsedTimer()
        timer.start()
        while self.window.state == UIState.LOADING and timer.elapsed() < 5000:
            QTest.qWait(10)
        self.assertNotEqual(self.window.state, UIState.LOADING, "CSV load timed out")

    def load_sample(self):
        self.window.select_csv(SAMPLE)
        QTest.mouseClick(self.window.check_button, Qt.MouseButton.LeftButton)
        self.wait_for_validation()
        self.assertEqual(self.window.state, UIState.READY)

    def wait_for_run(self):
        timer = QElapsedTimer()
        timer.start()
        while self.window.controller.running and timer.elapsed() < 3000:
            QTest.qWait(10)
        self.assertFalse(self.window.controller.running, "Simulation timed out")

    def wait_for_trace_rows(self, count):
        timer = QElapsedTimer()
        timer.start()
        while self.window.trace_table.rowCount() < count and timer.elapsed() < 3000:
            QTest.qWait(10)
        self.assertEqual(self.window.trace_table.rowCount(), count)

    def test_trace_appears_before_script_finishes_with_complete_fields(self):
        for mechanism_index, mechanism_name in (
            (0, "SHARED_MEMORY"),
            (2, "MESSAGE_QUEUE"),
        ):
            with self.subTest(mechanism=mechanism_name):
                self.load_sample()
                self.window.mechanism_combo.setCurrentIndex(mechanism_index)
                for step in self.window.messages:
                    step["delay_ms"] = 0
                self.window.messages[1]["delay_ms"] = 200
                self.window.messages[0]["id"] = 42
                first_step = dict(self.window.messages[0])
                self.window._start()
                self.wait_for_trace_rows(1)
                self.assertTrue(self.window.controller.running)
                values = [
                    self.window.trace_table.item(0, column).text()
                    for column in range(9)
                ]
                self.assertEqual(values[0], "1")
                self.assertIsNotNone(datetime.fromisoformat(values[1]).tzinfo)
                self.assertEqual(
                    values[2:7],
                    [
                        "42",
                        first_step["sender"],
                        first_step["action"],
                        mechanism_name,
                        "SUCCESS",
                    ],
                )
                self.assertGreaterEqual(float(values[7]), 0)
                self.assertTrue(values[8])
                self.assertEqual(self.window.trace_count_label.text(), "1 bản ghi")
                self.assertTrue(self.window.export_button.isEnabled())
                self.wait_for_run()
                self.assertEqual(self.window.trace_table.rowCount(), SAMPLE_COUNT)
                self.assertEqual(
                    [
                        self.window.trace_table.item(row, 0).text()
                        for row in range(SAMPLE_COUNT)
                    ],
                    [str(index) for index in range(1, SAMPLE_COUNT + 1)],
                )

    def test_pause_and_stop_preserve_trace_and_new_run_clears_old_rows(self):
        self.load_sample()
        for step in self.window.messages:
            step["delay_ms"] = 0
        self.window.messages[1]["delay_ms"] = 200
        self.window._start()
        self.wait_for_trace_rows(1)
        self.window._pause()
        QTest.qWait(250)
        self.assertEqual(self.window.trace_table.rowCount(), 1)
        self.window._start()
        self.wait_for_run()
        self.assertEqual(self.window.trace_table.rowCount(), SAMPLE_COUNT)
        self.window._start()
        self.wait_for_trace_rows(1)
        self.window._stop()
        QTest.qWait(250)
        self.assertEqual(self.window.trace_table.rowCount(), 1)
        self.assertTrue(self.window.export_button.isEnabled())
        self.window.messages[1]["delay_ms"] = 0
        self.window._start()
        self.assertEqual(self.window.trace_table.rowCount(), 0)
        self.assertEqual(self.window.trace_count_label.text(), "0 bản ghi")
        self.assertFalse(self.window.export_button.isEnabled())
        self.wait_for_run()
        self.assertEqual(self.window.trace_table.rowCount(), SAMPLE_COUNT)

    def test_reset_and_file_selection_clear_trace(self):
        self.load_sample()
        for step in self.window.messages:
            step["delay_ms"] = 0
        self.window.messages[1]["delay_ms"] = 200
        self.window._start()
        self.wait_for_trace_rows(1)
        self.window._reset()
        self.assertEqual(self.window.trace_table.rowCount(), 0)
        self.assertEqual(self.window.trace_count_label.text(), "0 bản ghi")
        self.assertFalse(self.window.export_button.isEnabled())
        self.window._start()
        self.wait_for_trace_rows(1)
        self.window._stop()
        self.window.select_csv(SAMPLE)
        self.assertEqual(self.window.trace_table.rowCount(), 0)
        self.assertFalse(self.window.export_button.isEnabled())

    def test_revalidation_clears_stale_trace_even_when_file_becomes_invalid(self):
        path = self.directory / "scenario.csv"
        path.write_text(SAMPLE.read_text(encoding="utf-8"), encoding="utf-8")
        self.window.select_csv(path)
        self.window.validate_csv()
        self.wait_for_validation()
        for step in self.window.messages:
            step["delay_ms"] = 0
        self.window._start()
        self.wait_for_run()
        self.assertEqual(self.window.trace_table.rowCount(), SAMPLE_COUNT)
        path.write_text("", encoding="utf-8")
        self.window.validate_csv()
        self.wait_for_validation()
        self.assertEqual(self.window.trace_table.rowCount(), 0)
        self.assertFalse(self.window.export_button.isEnabled())
        self.assertFalse(self.window.start_button.isEnabled())

    def test_trace_follows_latest_row_until_user_scrolls_up(self):
        self.window.show()
        self.app.processEvents()
        for index in range(60):
            self.window.append_trace(
                [
                    index + 1,
                    "time",
                    index,
                    "P1",
                    "SEND",
                    "SHARED_MEMORY",
                    "SUCCESS",
                    "0.1",
                    "detail",
                ]
            )
        self.app.processEvents()
        scrollbar = self.window.trace_table.verticalScrollBar()
        self.assertGreater(scrollbar.maximum(), 0)
        self.assertEqual(scrollbar.value(), scrollbar.maximum())
        scrollbar.setValue(0)
        self.window.append_trace(
            [61, "time", 61, "P1", "SEND", "SHARED_MEMORY", "BLOCKED", "0.1", "full"]
        )
        self.app.processEvents()
        self.assertEqual(scrollbar.value(), 0)
        self.assertEqual(self.window.trace_count_label.text(), "61 bản ghi")

    def test_browse_loads_and_validates_csv_automatically(self):
        with patch(
            "src.gui.main_window.QFileDialog.getOpenFileName",
            return_value=(str(SAMPLE), "CSV (*.csv)"),
        ):
            QTest.mouseClick(self.window.browse_button, Qt.MouseButton.LeftButton)
        self.wait_for_validation()
        self.assertEqual(self.window.state, UIState.READY)
        self.assertEqual(len(self.window.messages), SAMPLE_COUNT)
        self.assertTrue(self.window.start_button.isEnabled())

    def test_script_executes_real_ipc_and_can_run_again(self):
        for mechanism in (0, 2):
            with self.subTest(mechanism=mechanism):
                self.load_sample()
                self.window.mechanism_combo.setCurrentIndex(mechanism)
                for step in self.window.messages:
                    step["delay_ms"] = 0
                completed = QSignalSpy(self.window.controller.step_completed)
                finished = QSignalSpy(self.window.controller.finished)
                self.window._start()
                self.assertFalse(self.window.start_button.isEnabled())
                self.window._start()  # A second request must not create a second run.
                self.wait_for_run()
                self.assertEqual(len(completed), SAMPLE_COUNT)
                self.assertEqual(len(finished), 1)
                self.assertEqual(
                    [row[0]["snapshot"]["count"] for row in completed],
                    [1, 0, 1, 0, 1, 0, 1, 0, 1, 0],
                )
                self.assertTrue(all(row[0]["result"].success for row in completed))
                self.assertEqual(self.window.state, UIState.READY)
                self.assertEqual(
                    self.window.processed_steps_label.text(), str(SAMPLE_COUNT)
                )
                self.assertEqual(self.window.buffer_progress.value(), 0)
                self.assertFalse(self.window.stop_button.isEnabled())
                self.window._start()
                self.assertEqual(
                    self.window.controller.mechanism.get_state()["count"], 0
                )
                self.wait_for_run()
                self.assertEqual(len(completed), 2 * SAMPLE_COUNT)

    def test_full_and_empty_steps_report_blocked_without_hanging(self):
        for mechanism in (0, 2):
            with self.subTest(mechanism=mechanism):
                self.load_sample()
                self.window.mechanism_combo.setCurrentIndex(mechanism)
                self.window.buffer_spin.setValue(1)
                template = self.window.messages[0]
                self.window.messages = [
                    dict(
                        template,
                        id=index,
                        action=action,
                        delay_ms=0,
                        message="hello" if action in ("PRODUCE", "SEND") else "",
                    )
                    for index, action in enumerate(
                        ("SEND", "PRODUCE", "RECEIVE", "CONSUME"), start=1
                    )
                ]
                completed = QSignalSpy(self.window.controller.step_completed)
                self.window._start()
                self.wait_for_run()
                self.assertEqual(
                    [row[0]["result"].status for row in completed],
                    ["SUCCESS", "BLOCKED", "SUCCESS", "BLOCKED"],
                )
                self.assertEqual(self.window.failed_steps_label.text(), "2")
                self.assertEqual(self.window.buffer_progress.value(), 0)
                self.assertEqual(
                    [self.window.trace_table.item(row, 6).text() for row in range(4)],
                    ["SUCCESS", "BLOCKED", "SUCCESS", "BLOCKED"],
                )

    def test_stop_during_delay_is_responsive_and_restart_begins_at_first_step(self):
        self.load_sample()
        for step in self.window.messages:
            step["delay_ms"] = 1000
        completed = QSignalSpy(self.window.controller.step_completed)
        ticks = []
        self.window._start()
        QTimer.singleShot(0, lambda: ticks.append(True))
        QTest.qWait(20)
        self.assertTrue(ticks)
        self.assertTrue(self.window.stop_button.isEnabled())
        QTest.mouseClick(self.window.stop_button, Qt.MouseButton.LeftButton)
        QTest.qWait(40)
        self.assertFalse(self.window.controller.running)
        self.assertFalse(self.window.controller.timer.isActive())
        self.assertEqual(len(completed), 0)
        self.assertEqual(self.window.state, UIState.READY)
        self.assertEqual(len(self.window.messages), SAMPLE_COUNT)
        for step in self.window.messages:
            step["delay_ms"] = 0
        self.window._start()
        self.wait_for_run()
        self.assertEqual(completed[0][0]["step"]["id"], 1)
        self.assertEqual(len(completed), SAMPLE_COUNT)

    def test_pause_suspends_pending_step_and_resume_completes(self):
        self.load_sample()
        for step in self.window.messages:
            step["delay_ms"] = 0
        self.window.messages[0]["delay_ms"] = 100
        completed = QSignalSpy(self.window.controller.step_completed)
        self.window._start()
        self.window._pause()
        QTest.qWait(150)
        self.assertEqual(len(completed), 0)
        self.assertEqual(self.window.state, UIState.PAUSED)
        self.assertTrue(self.window.stop_button.isEnabled())
        self.window._start()
        self.wait_for_run()
        self.assertEqual(len(completed), SAMPLE_COUNT)

    def test_stop_while_paused_and_reset_clear_run_state(self):
        self.load_sample()
        self.window._start()
        self.window._pause()
        self.window._stop()
        self.assertEqual(self.window.state, UIState.READY)
        self.assertFalse(self.window.controller.paused)
        self.window._start()
        self.window._pause()
        self.window.buffer_progress.setValue(2)
        self.window.processed_steps_label.setText("3")
        self.window._reset()
        self.assertIsNone(self.window.controller.mechanism)
        self.assertFalse(self.window.controller.timer.isActive())
        self.assertEqual(self.window.buffer_progress.value(), 0)
        self.assertEqual(self.window.processed_steps_label.text(), "0")
        self.assertEqual(len(self.window.messages), SAMPLE_COUNT)

    def test_unsupported_mechanism_keeps_ui_ready(self):
        self.load_sample()
        self.window.mechanism_combo.setCurrentIndex(1)
        start = QSignalSpy(self.window.start_requested)
        self.window._start()
        self.assertEqual(len(start), 0)
        self.assertEqual(self.window.state, UIState.READY)
        self.assertTrue(self.window.start_button.isEnabled())
        self.assertIn("chưa được hỗ trợ", self.window.statusBar().currentMessage())

    def test_ipc_error_returns_to_ready_and_allows_restart(self):
        self.load_sample()
        self.window.messages[0]["delay_ms"] = 0
        with patch(
            "src.gui.simulation_controller.SharedMemory.produce",
            side_effect=RuntimeError("test failure"),
        ):
            self.window._start()
            self.wait_for_run()
        self.assertEqual(self.window.state, UIState.READY)
        self.assertIn("test failure", self.window.statusBar().currentMessage())
        self.assertEqual(self.window.trace_table.rowCount(), 1)
        self.assertEqual(self.window.trace_table.item(0, 6).text(), "ERROR")
        self.assertIn("test failure", self.window.trace_table.item(0, 8).text())
        self.window._start()
        self.assertTrue(self.window.controller.running)
        self.window._stop()

    def test_close_stops_pending_simulation(self):
        self.load_sample()
        self.window.messages[0]["delay_ms"] = 1000
        self.window._start()
        self.window.close()
        self.assertFalse(self.window.controller.running)
        self.assertFalse(self.window.controller.timer.isActive())

    def test_start_requires_successful_validation(self):
        self.assertFalse(self.window.start_button.isEnabled())
        self.assertFalse(self.window.pause_button.isEnabled())
        self.assertFalse(self.window.reset_button.isEnabled())
        self.window.select_csv(SAMPLE)
        self.assertFalse(self.window.start_button.isEnabled())
        self.assertTrue(self.window.check_button.isEnabled())
        self.window.validate_csv()
        self.wait_for_validation()
        self.assertTrue(self.window.start_button.isEnabled())
        self.assertEqual(self.window.row_count_label.text(), str(SAMPLE_COUNT))
        self.assertEqual(self.window.messages[0]["id"], 1)
        self.assertEqual(self.window.trace_table.rowCount(), 0)

    def test_error_then_valid_file(self):
        for contents, detail in (
            ("", "rỗng"),
            ("id,action\n1,PRODUCE\n", "thiếu cột"),
            ("id,action,sender,receiver\nabc,SEND,P1,C1\n", "số nguyên"),
            ("id,action,sender,receiver\n1,UNKNOWN,P1,C1\n", "action"),
        ):
            with self.subTest(detail=detail):
                path = self.directory / "bad.csv"
                path.write_text(contents, encoding="utf-8")
                self.window.select_csv(path)
                self.window.validate_csv()
                self.wait_for_validation()
                self.assertIn("INVALID_DATA", self.window.file_feedback.text())
                self.assertIn(detail, self.window.file_feedback.text())
                self.assertFalse(self.window.start_button.isEnabled())
                self.assertEqual(self.window.messages, [])
                self.assertTrue(self.window.browse_button.isEnabled())
        self.load_sample()

    def test_removed_file_does_not_leave_old_data_ready(self):
        self.load_sample()
        self.window.select_csv(self.directory / "missing.csv")
        self.window.validate_csv()
        self.wait_for_validation()
        self.assertIn("FILE_READ_ERROR", self.window.file_feedback.text())
        self.assertFalse(self.window.start_button.isEnabled())
        self.assertEqual(self.window.messages, [])
        self.assertEqual(self.window.total_steps_label.text(), "0")

    def test_malformed_csv_and_invalid_encoding_are_reported(self):
        for content, code in (
            (b'id,action,sender,receiver\n1,SEND,P1,"C1\n', "INVALID_CSV"),
            (b"\xff\xfe\xff", "FILE_READ_ERROR"),
        ):
            with self.subTest(code=code):
                path = self.directory / "bad.csv"
                path.write_bytes(content)
                self.window.select_csv(path)
                self.window.validate_csv()
                self.wait_for_validation()
                self.assertIn(code, self.window.file_feedback.text())
                self.assertFalse(self.window.start_button.isEnabled())
                self.assertEqual(self.window.messages, [])

    def test_start_pause_resume_reset_signals_and_configuration(self):
        self.load_sample()
        self.window.mechanism_combo.setCurrentIndex(2)
        self.window.buffer_spin.setValue(8)
        self.window.producer_spin.setValue(3)
        self.window.consumer_spin.setValue(2)
        start = QSignalSpy(self.window.start_requested)
        pause = QSignalSpy(self.window.pause_requested)
        resume = QSignalSpy(self.window.resume_requested)
        reset = QSignalSpy(self.window.reset_requested)
        QTest.mouseClick(self.window.start_button, Qt.MouseButton.LeftButton)
        self.assertEqual(len(start), 1)
        self.assertEqual(len(start[0][0]), SAMPLE_COUNT)
        self.assertEqual(
            start[0][1],
            {
                "mechanism": "MESSAGE_QUEUE",
                "buffer_capacity": 8,
                "producer_count": 3,
                "consumer_count": 2,
            },
        )
        self.assertFalse(self.window.browse_button.isEnabled())
        self.assertFalse(self.window.buffer_spin.isEnabled())
        QTest.mouseClick(self.window.pause_button, Qt.MouseButton.LeftButton)
        self.assertEqual(len(pause), 1)
        self.assertEqual(self.window.state, UIState.PAUSED)
        QTest.mouseClick(self.window.start_button, Qt.MouseButton.LeftButton)
        self.assertEqual(len(resume), 1)
        self.assertEqual(len(start), 1)
        QTest.mouseClick(self.window.reset_button, Qt.MouseButton.LeftButton)
        self.assertEqual(len(reset), 1)
        self.assertEqual(self.window.state, UIState.READY)
        self.assertEqual(len(self.window.messages), SAMPLE_COUNT)
        self.assertTrue(self.window.buffer_spin.isEnabled())

    def test_validation_runs_without_blocking_ui(self):
        release = threading.Event()
        parse = CSVParser().parse

        def slow_parse(path):
            release.wait(3)
            return parse(path)

        with patch("src.gui.main_window.CSVParser.parse", side_effect=slow_parse):
            try:
                self.window.select_csv(SAMPLE)
                self.window.validate_csv()
                self.assertEqual(self.window.state, UIState.LOADING)
                self.assertFalse(self.window.browse_button.isEnabled())
                self.assertFalse(self.window.check_button.isEnabled())
                ticks = []
                QTimer.singleShot(0, lambda: ticks.append(True))
                QTest.qWait(20)
                self.assertTrue(ticks, "UI event loop did not process the timer")
                self.window.select_csv(self.directory / "other.csv")
                self.assertEqual(self.window.selected_path, SAMPLE)
            finally:
                release.set()
                self.wait_for_validation()

    def test_cancel_file_dialog_keeps_valid_selection(self):
        self.load_sample()
        with patch(
            "src.gui.main_window.QFileDialog.getOpenFileName", return_value=("", "")
        ):
            QTest.mouseClick(self.window.browse_button, Qt.MouseButton.LeftButton)
        self.assertEqual(self.window.selected_path, SAMPLE)
        self.assertEqual(self.window.state, UIState.READY)

    def test_export_trace_preserves_csv_content_and_reset_clears_it(self):
        self.load_sample()
        self.assertFalse(self.window.export_button.isEnabled())
        trace = [
            1,
            "2026-10-18 10:00:00",
            1,
            "P1",
            "SEND",
            "SHARED_MEMORY",
            "SUCCESS",
            12,
            'Gửi tin nhắn, "xin chào"\nDòng hai',
        ]
        self.window.append_trace(trace)
        self.assertTrue(self.window.export_button.isEnabled())
        path = self.directory / "trace.csv"
        self.assertTrue(self.window.export_trace(path))
        with path.open(encoding="utf-8-sig", newline="") as stream:
            rows = list(csv.reader(stream))
        self.assertEqual(rows[0], list(self.window.TRACE_COLUMNS))
        self.assertEqual(rows[1], [str(value) for value in trace])
        self.window._start()
        self.window._reset()
        self.assertEqual(self.window.trace_table.rowCount(), 0)
        self.assertFalse(self.window.export_button.isEnabled())

    def test_export_failure_is_reported_without_exception(self):
        self.assertFalse(
            self.window.export_trace(self.directory / "missing" / "trace.csv")
        )
        self.assertIn("Không thể xuất trace", self.window.statusBar().currentMessage())

    def test_capacity_updates_visualization(self):
        self.window.buffer_spin.setValue(1024)
        self.assertEqual(self.window.buffer_slots.capacity, 1024)
        self.assertEqual(self.window.buffer_count_label.text(), "Đang chứa: 0 / 1024")
        # Vẽ thực sự để kiểm tra widget ở dung lượng lớn vẫn hoạt động.
        self.window.show()
        self.app.processEvents()
        self.assertFalse(self.window.grab().isNull())

    def test_default_layout_shows_all_panels_without_scrolling(self):
        self.window.show()
        self.app.processEvents()
        scroll = self.window.centralWidget()
        self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
        self.assertEqual(scroll.verticalScrollBar().maximum(), 0)
        self.assertTrue(self.window.export_button.isVisible())


if __name__ == "__main__":
    unittest.main()
