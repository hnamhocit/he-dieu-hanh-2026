"""Kiểm thử nạp CSV, điều khiển và xuất trace trên Qt offscreen."""

import csv
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QElapsedTimer, QEvent, QThreadPool, QTimer, Qt
from PyQt6.QtGui import QFont, QFontDatabase
from PyQt6.QtTest import QSignalSpy, QTest
from PyQt6.QtWidgets import QApplication

from src.gui.main_window import MainWindow, UIState
from src.utils.csv_parser import CSVParser


SAMPLE = Path(__file__).resolve().parents[1] / "data/input/sample_messages.csv"


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
        self.assertEqual(self.window.row_count_label.text(), "7")
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
        self.assertEqual(len(start[0][0]), 7)
        self.assertEqual(start[0][1], {
            "mechanism": "MESSAGE_QUEUE", "buffer_capacity": 8,
            "producer_count": 3, "consumer_count": 2,
        })
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
        self.assertEqual(len(self.window.messages), 7)
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
        with patch("src.gui.main_window.QFileDialog.getOpenFileName", return_value=("", "")):
            QTest.mouseClick(self.window.browse_button, Qt.MouseButton.LeftButton)
        self.assertEqual(self.window.selected_path, SAMPLE)
        self.assertEqual(self.window.state, UIState.READY)

    def test_export_trace_preserves_csv_content_and_reset_clears_it(self):
        self.load_sample()
        self.assertFalse(self.window.export_button.isEnabled())
        trace = [1, "2026-10-18 10:00:00", 1, "P1", "SEND", "SHARED_MEMORY",
                 "SUCCESS", 12, 'Gửi tin nhắn, "xin chào"\nDòng hai']
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
        self.assertFalse(self.window.export_trace(self.directory / "missing" / "trace.csv"))
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
