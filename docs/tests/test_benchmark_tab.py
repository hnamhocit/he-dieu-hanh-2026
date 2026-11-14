"""Kiểm tra worker, trạng thái GUI và kết quả biểu đồ trên Qt offscreen."""

import os
import threading
from unittest.mock import patch

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.setdefault("MPLCONFIGDIR", "/tmp/hdh110-matplotlib")

from PyQt6.QtCore import QThreadPool, QTimer
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from src.core.benchmark import BenchmarkCancelled
from src.gui.main_window import MainWindow


def wait_finished(tab):
    for _ in range(500):
        if tab.worker is None:
            return
        QTest.qWait(10)
    raise AssertionError("Benchmark worker timed out")


def test_tab_runs_and_can_run_again():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    try:
        tab = window.benchmark_tab
        # Qt dùng && để hiển thị ký tự & thay vì tạo phím tắt.
        assert window.tabs.tabText(1) == "Benchmark && Analysis"
        tab.message_spin.setValue(11)
        tab.capacity_spin.setValue(4)
        tab.repeats_spin.setValue(1)
        tab.start()
        worker = tab.worker
        tab.start()
        assert tab.worker is worker
        assert not tab.run_button.isEnabled()
        wait_finished(tab)
        assert tab.table.rowCount() == 2
        assert tab.progress.value() == tab.progress.maximum() == 2
        assert len(tab.throughput_axes.lines) == len(tab.latency_axes.lines) == 2
        assert tab.run_button.isEnabled()
        tab.mechanism_combo.setCurrentIndex(2)
        tab.start()
        wait_finished(tab)
        assert tab.table.rowCount() == 1
        assert tab.results[0].mechanism == "MESSAGE_QUEUE"
        assert len(tab.throughput_axes.lines) == 1
    finally:
        window.close()
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()


def test_worker_error_and_cancel_leave_gui_responsive():
    app = QApplication.instance() or QApplication([])
    window = MainWindow()
    tab = window.benchmark_tab
    try:
        with patch("src.gui.benchmark_tab.run_benchmark", side_effect=RuntimeError("test failure")):
            tab.start()
            wait_finished(tab)
        assert "test failure" in tab.status_label.text()
        assert tab.run_button.isEnabled()
        caller_threads = []

        def slow_run(config, cancel, on_result):
            caller_threads.append(threading.get_ident())
            assert cancel.wait(5), "UI cancellation did not reach the worker"
            raise BenchmarkCancelled()

        with patch("src.gui.benchmark_tab.run_benchmark", side_effect=slow_run):
            tab.start()
            QTimer.singleShot(30, tab.cancel)
            wait_finished(tab)
        assert caller_threads[0] != threading.get_ident()
        assert "Đã dừng" in tab.status_label.text()
        assert tab.run_button.isEnabled()
        assert not tab.cancel_button.isEnabled()
        assert tab.table.rowCount() == 0
    finally:
        window.close()
        QThreadPool.globalInstance().waitForDone(5000)
        app.processEvents()
