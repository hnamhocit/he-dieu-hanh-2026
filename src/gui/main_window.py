"""Giao diện IPC: nạp CSV và điều khiển bộ chạy kịch bản HDH-41."""

from __future__ import annotations

import csv
from dataclasses import asdict
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QAbstractScrollArea,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStyle,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.gui.styles import STYLESHEET
from src.gui.widgets import BufferChart, BufferSlots
from src.gui.simulation_controller import SimulationController
from src.utils.csv_parser import CSVParser


class UIState(str, Enum):
    EMPTY = "Chưa chọn file"
    SELECTED = "Chưa kiểm tra"
    LOADING = "Đang kiểm tra"
    READY = "Sẵn sàng"
    RUNNING = "Đang chạy"
    PAUSED = "Đang tạm dừng"


class _LoadSignals(QObject):
    finished = pyqtSignal(object)


class _CSVLoader(QRunnable):
    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self.signals = _LoadSignals()

    @pyqtSlot()
    def run(self):
        # Dùng parser đã có trên main, không phụ thuộc module của HDH-31.
        try:
            steps = CSVParser().parse(self.path)
        except (OSError, UnicodeError) as error:
            result = {
                "success": False,
                "error_code": "FILE_READ_ERROR",
                "detail": str(error),
                "data": [],
            }
        except csv.Error as error:
            result = {
                "success": False,
                "error_code": "INVALID_CSV",
                "detail": str(error),
                "data": [],
            }
        except ValueError as error:
            result = {
                "success": False,
                "error_code": "INVALID_DATA",
                "detail": str(error),
                "data": [],
            }
        else:
            result = {
                "success": True,
                "error_code": "OK",
                "detail": "",
                "data": [asdict(step) for step in steps],
            }
        self.signals.finished.emit(result)


def _label(text: str = "", name: str = "") -> QLabel:
    label = QLabel(text)
    label.setTextFormat(Qt.TextFormat.PlainText)
    if name:
        label.setObjectName(name)
    return label


class MainWindow(QMainWindow):
    start_requested = pyqtSignal(list, dict)
    pause_requested = pyqtSignal()
    resume_requested = pyqtSignal()
    reset_requested = pyqtSignal()
    stop_requested = pyqtSignal()

    TRACE_COLUMNS = (
        "#",
        "Timestamp",
        "Step",
        "Process",
        "Action",
        "Mechanism",
        "Status",
        "Latency (ms)",
        "Detail",
    )

    def __init__(self):
        super().__init__()
        self.selected_path: Path | None = None
        self.messages: list[dict] = []
        self.state = UIState.EMPTY
        self._loader = None
        self.setWindowTitle("OS_IPC_09 - Desktop IPC Simulator")
        self.resize(1180, 910)
        self.setMinimumSize(940, 700)
        self.setStyleSheet(STYLESHEET)
        self._build_layout()
        self.controller = SimulationController(self)

        self.start_requested.connect(self.controller.start)
        self.pause_requested.connect(self.controller.pause)
        self.resume_requested.connect(self.controller.resume)
        self.reset_requested.connect(self.controller.reset)
        self.stop_requested.connect(self.controller.stop)

        self.controller.step_completed.connect(self._on_step_completed)
        self.controller.trace_recorded.connect(self._on_trace_recorded)
        self.controller.finished.connect(self._on_simulation_finished)
        self._set_state(UIState.EMPTY)
        self.statusBar().showMessage(
            "Nạp file CSV hợp lệ → Chọn cấu hình → Bắt đầu chạy."
        )

    def _build_layout(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(scroll)
        page = QWidget()
        page.setObjectName("page")
        scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        title = QFrame()
        title.setObjectName("titleBar")
        title_row = QHBoxLayout(title)
        title_row.addWidget(_label("▣  OS_IPC_09 - Desktop IPC Simulator", "appTitle"))
        title_row.addStretch()
        title_row.addWidget(_label("MÔ PHỎNG IPC", "modeBadge"))
        layout.addWidget(title)

        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self._build_csv_panel(), 1)
        top.addWidget(self._build_config_panel(), 1)
        layout.addLayout(top)
        layout.addWidget(self._build_buffer_panel(), 3)
        layout.addWidget(self._build_trace_panel(), 2)
        layout.addWidget(
            _label(
                "① Nạp CSV    →    ② Cấu hình    →    ③ Bắt đầu / Tạm dừng / Dừng"
                "    →    ④ Theo dõi kết quả",
                "flow",
            )
        )

    def _build_csv_panel(self):
        group = QGroupBox("▣  CSV Input")
        layout = QVBoxLayout(group)
        row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        self.file_path.setPlaceholderText("Chưa chọn file…")
        self.file_path.setAccessibleName("Đường dẫn file CSV")
        self.browse_button = QPushButton("Nạp file CSV")
        self.browse_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton)
        )
        self.check_button = QPushButton("Kiểm tra")
        self.check_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
        )
        self.browse_button.clicked.connect(self._choose_file)
        self.check_button.clicked.connect(self.validate_csv)
        row.addWidget(self.file_path, 1)
        row.addWidget(self.browse_button)
        row.addWidget(self.check_button)
        layout.addLayout(row)
        info = QFrame()
        info.setObjectName("fileInfo")
        form = QFormLayout(info)
        self.file_name_label = _label("—")
        self.file_name_label.setWordWrap(True)
        self.row_count_label = _label("0")
        self.file_size_label = _label("0 KB")
        self.file_state_label = _label()
        form.addRow("Tên file:", self.file_name_label)
        form.addRow("Số dòng dữ liệu:", self.row_count_label)
        form.addRow("Kích thước:", self.file_size_label)
        form.addRow("Trạng thái:", self.file_state_label)
        layout.addWidget(info)
        self.file_feedback = _label("Chọn CSV UTF-8 để kiểm tra dữ liệu đầu vào.")
        self.file_feedback.setWordWrap(True)
        layout.addWidget(self.file_feedback)
        return group

    def _build_config_panel(self):
        group = QGroupBox("⚙  Cấu hình tham số")
        group.setObjectName("configGroup")
        layout = QVBoxLayout(group)
        grid = QGridLayout()
        self.mechanism_combo = QComboBox()
        for title, value in (
            ("Shared Memory", "SHARED_MEMORY"),
            ("Pipe", "PIPE"),
            ("Message Queue", "MESSAGE_QUEUE"),
        ):
            self.mechanism_combo.addItem(title, value)
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(1, 1024)
        self.buffer_spin.setValue(5)
        self.producer_spin = QSpinBox()
        self.producer_spin.setRange(1, 64)
        self.consumer_spin = QSpinBox()
        self.consumer_spin.setRange(1, 64)
        for label, widget, row, column in (
            ("Cơ chế IPC", self.mechanism_combo, 0, 0),
            ("Số tiến trình Producer", self.producer_spin, 0, 1),
            ("Dung lượng Buffer", self.buffer_spin, 2, 0),
            ("Số tiến trình Consumer", self.consumer_spin, 2, 1),
        ):
            text = _label(label)
            text.setBuddy(widget)
            grid.addWidget(text, row, column)
            grid.addWidget(widget, row + 1, column)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        controls = QHBoxLayout()
        self.start_button = QPushButton("Bắt đầu chạy")
        self.pause_button = QPushButton("Tạm dừng")
        self.reset_button = QPushButton("Reset")
        self.stop_button = QPushButton("Dừng")
        self.stop_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaStop)
        )
        self.start_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.pause_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause)
        )
        self.reset_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload)
        )
        for button, name, callback in (
            (self.start_button, "startButton", self._start),
            (self.pause_button, "pauseButton", self._pause),
            (self.stop_button, "stopButton", self._stop),
            (self.reset_button, "resetButton", self._reset),
        ):
            button.setObjectName(name)
            button.clicked.connect(callback)
            controls.addWidget(button, 1)
        layout.addLayout(controls)
        self.control_state_label = _label("Chưa chọn file")
        layout.addWidget(self.control_state_label)
        self.buffer_spin.valueChanged.connect(self._capacity_changed)
        return group

    def _actor_card(self, title, name, counter_labels):
        card = QFrame()
        card.setObjectName(name)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.addWidget(_label(title, "cardTitle"))
        for text in counter_labels:
            layout.addWidget(_label(text))
        badge = _label("Sẵn sàng", "readyBadge")
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignLeft)
        return card

    def _build_buffer_panel(self):
        group = QGroupBox("▥  Buffer Visualization")
        group.setObjectName("bufferGroup")
        layout = QVBoxLayout(group)
        actors = QHBoxLayout()
        actors.addWidget(
            self._actor_card(
                "◉  Producer", "producerCard", ("Đang gửi:     0", "Đã gửi:         0")
            ),
            3,
        )
        actors.addWidget(_label("→", "arrow"))
        buffer_card = QFrame()
        buffer_card.setObjectName("bufferCard")
        buffer_layout = QVBoxLayout(buffer_card)
        buffer_layout.addWidget(_label("▤  Shared Buffer / Message Queue", "cardTitle"))
        self.buffer_slots = BufferSlots()
        buffer_layout.addWidget(self.buffer_slots)
        self.buffer_count_label = _label("Đang chứa: 0 / 5")
        buffer_layout.addWidget(self.buffer_count_label)
        progress_row = QHBoxLayout()
        self.buffer_progress = QProgressBar()
        self.buffer_progress.setRange(0, 5)
        self.buffer_progress.setValue(0)
        self.buffer_progress.setTextVisible(False)
        progress_row.addWidget(self.buffer_progress, 1)
        self.buffer_percent_label = _label("0%")
        progress_row.addWidget(self.buffer_percent_label)
        buffer_layout.addLayout(progress_row)
        actors.addWidget(buffer_card, 4)
        actors.addWidget(_label("→", "arrow"))
        actors.addWidget(
            self._actor_card(
                "◉  Consumer", "consumerCard", ("Đã nhận:       0", "Đã xử lý:       0")
            ),
            3,
        )
        layout.addLayout(actors)

        lower = QHBoxLayout()
        chart = QFrame()
        chart.setObjectName("chartCard")
        chart_layout = QVBoxLayout(chart)
        chart_layout.addWidget(
            _label("▥  Mức sử dụng Buffer theo thời gian", "cardTitle")
        )
        chart_layout.addWidget(BufferChart())
        lower.addWidget(chart, 7)
        stats = QFrame()
        stats.setObjectName("statsCard")
        stats_layout = QVBoxLayout(stats)
        stats_layout.addWidget(_label("Thống kê nhanh", "cardTitle"))
        stats_form = QFormLayout()
        self.total_steps_label = _label("0")
        stats_form.addRow("Tổng số bước", self.total_steps_label)
        self.processed_steps_label = _label("0")
        self.failed_steps_label = _label("0")
        stats_form.addRow("Đã xử lý", self.processed_steps_label)
        stats_form.addRow("Bước không thành công", self.failed_steps_label)
        stats_form.addRow("Throughput (msg/s)", _label("0"))
        stats_layout.addLayout(stats_form)
        stats_layout.addStretch()
        lower.addWidget(stats, 3)
        layout.addLayout(lower)
        return group

    def _build_trace_panel(self):
        group = QGroupBox("▧  Trace Log")
        group.setObjectName("traceGroup")
        layout = QVBoxLayout(group)
        self.trace_table = QTableWidget(0, len(self.TRACE_COLUMNS))
        self.trace_table.setHorizontalHeaderLabels(self.TRACE_COLUMNS)
        self.trace_table.verticalHeader().hide()
        self.trace_table.setAlternatingRowColors(True)
        self.trace_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.trace_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.trace_table.setMinimumHeight(110)
        self.trace_table.setWordWrap(False)
        self.trace_table.setSizeAdjustPolicy(
            QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents
        )
        header = self.trace_table.horizontalHeader()
        header.setDefaultSectionSize(100)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.trace_table.setColumnWidth(0, 36)
        self.trace_table.setColumnWidth(1, 155)
        layout.addWidget(self.trace_table)
        row = QHBoxLayout()
        self.trace_count_label = _label("0 bản ghi")
        row.addWidget(self.trace_count_label)
        row.addStretch()
        self.export_button = QPushButton("Xuất Trace CSV")
        self.export_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton)
        )
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._choose_export_path)
        row.addWidget(self.export_button)
        layout.addLayout(row)
        return group

    @pyqtSlot()
    def _choose_file(self):
        directory = Path(__file__).resolve().parents[2] / "data" / "input"
        path, _ = QFileDialog.getOpenFileName(
            self, "Chọn file CSV", str(directory), "CSV (*.csv)"
        )
        if path:
            self.select_csv(path)
            self.validate_csv()

    def select_csv(self, path: str | Path):
        if self.state in (UIState.LOADING, UIState.RUNNING, UIState.PAUSED):
            return
        self.selected_path = Path(path)
        self.messages = []
        self.file_path.setText(str(self.selected_path))
        self.file_path.setToolTip(str(self.selected_path))
        self.file_name_label.setText(self.selected_path.name)
        self.row_count_label.setText("0")
        self.total_steps_label.setText("0")
        self._clear_run_display()
        self._clear_trace()
        try:
            self.file_size_label.setText(
                f"{self.selected_path.stat().st_size / 1024:.2f} KB"
            )
        except OSError:
            self.file_size_label.setText("Không xác định")
        self.file_feedback.setStyleSheet("")
        self.file_feedback.setText("Nhấn Kiểm tra để xác nhận dữ liệu CSV.")
        self._set_state(UIState.SELECTED)

    @pyqtSlot()
    def validate_csv(self):
        if self.selected_path is None or self.state not in (
            UIState.SELECTED,
            UIState.READY,
        ):
            return
        self.messages = []
        self.row_count_label.setText("0")
        self.total_steps_label.setText("0")
        self._clear_trace()
        self.file_feedback.setStyleSheet("")
        self.file_feedback.setText("Đang đọc và kiểm tra CSV…")
        self._set_state(UIState.LOADING)
        self._loader = _CSVLoader(self.selected_path)
        self._loader.signals.finished.connect(self._on_csv_loaded)
        QThreadPool.globalInstance().start(self._loader)

    @pyqtSlot(object)
    def _on_csv_loaded(self, result):
        if not result["success"]:
            self._set_state(UIState.SELECTED)
            self.file_state_label.setText("Không hợp lệ")
            self.file_feedback.setStyleSheet("color: #b42318;")
            self.file_feedback.setText(f'{result["error_code"]}: {result["detail"]}')
            return
        self.messages = result["data"]
        self.row_count_label.setText(str(len(self.messages)))
        self.total_steps_label.setText(str(len(self.messages)))
        self.file_feedback.setStyleSheet("color: #14745b;")
        self.file_feedback.setText("CSV hợp lệ. Chọn cấu hình rồi nhấn Bắt đầu chạy.")
        self._set_state(UIState.READY)

    def configuration(self) -> dict:
        return {
            "mechanism": self.mechanism_combo.currentData(),
            "buffer_capacity": self.buffer_spin.value(),
            "producer_count": self.producer_spin.value(),
            "consumer_count": self.consumer_spin.value(),
        }

    def _set_state(self, state: UIState):
        self.state = state
        editable = state in (UIState.EMPTY, UIState.SELECTED, UIState.READY)
        self.browse_button.setEnabled(editable)
        self.check_button.setEnabled(state in (UIState.SELECTED, UIState.READY))
        for widget in (
            self.mechanism_combo,
            self.buffer_spin,
            self.producer_spin,
            self.consumer_spin,
        ):
            widget.setEnabled(editable)
        self.start_button.setEnabled(state in (UIState.READY, UIState.PAUSED))
        self.start_button.setText(
            "Tiếp tục" if state == UIState.PAUSED else "Bắt đầu chạy"
        )
        self.pause_button.setEnabled(state == UIState.RUNNING)
        self.stop_button.setEnabled(state in (UIState.RUNNING, UIState.PAUSED))
        self.reset_button.setEnabled(state in (UIState.RUNNING, UIState.PAUSED))
        self.file_state_label.setText("Hợp lệ" if self.messages else state.value)
        self.control_state_label.setText(state.value)

    @pyqtSlot(int)
    def _capacity_changed(self, capacity):
        self.buffer_slots.set_capacity(capacity)
        self.buffer_count_label.setText(f"Đang chứa: 0 / {capacity}")
        self.buffer_progress.setRange(0, capacity)
        self.buffer_progress.setValue(0)
        self.buffer_percent_label.setText("0%")

    def _clear_run_display(self):
        self._capacity_changed(self.buffer_spin.value())
        self.processed_steps_label.setText("0")
        self.failed_steps_label.setText("0")

    @pyqtSlot()
    def _start(self):
        if self.state not in (UIState.READY, UIState.PAUSED):
            return
        if self.state == UIState.PAUSED:
            self._set_state(UIState.RUNNING)
            self.statusBar().showMessage("Đang tiếp tục mô phỏng.")
            self.resume_requested.emit()
            return
        configuration = self.configuration()
        if configuration["mechanism"] not in ("SHARED_MEMORY", "MESSAGE_QUEUE"):
            self.statusBar().showMessage(
                "Cơ chế này chưa được hỗ trợ. Hãy chọn Shared Memory hoặc Message Queue."
            )
            return
        self._clear_trace()
        self._clear_run_display()
        self._set_state(UIState.RUNNING)
        self.statusBar().showMessage("Đang chạy mô phỏng.")
        self.start_requested.emit(self.messages, configuration)

    @pyqtSlot()
    def _pause(self):
        if self.state == UIState.RUNNING:
            self._set_state(UIState.PAUSED)
            self.pause_requested.emit()
            self.statusBar().showMessage("Đã tạm dừng. Nhấn Tiếp tục để chạy tiếp.")

    @pyqtSlot()
    def _stop(self):
        if self.state in (UIState.RUNNING, UIState.PAUSED):
            self.stop_requested.emit()

    @pyqtSlot(dict)
    def _on_step_completed(self, event):
        snapshot = event["snapshot"]
        result = event["result"]
        step = event["step"]
        count, capacity = snapshot["count"], snapshot["capacity"]
        self.buffer_progress.setRange(0, capacity)
        self.buffer_progress.setValue(count)
        self.buffer_count_label.setText(f"Đang chứa: {count} / {capacity}")
        self.buffer_percent_label.setText(f"{count * 100 // capacity}%")
        self.processed_steps_label.setText(str(event["completed"]))
        if not result.success:
            self.failed_steps_label.setText(
                str(int(self.failed_steps_label.text()) + 1)
            )
        self.control_state_label.setText(
            f"Đang chạy: {event['completed']}/{event['total']} bước"
        )
        self.statusBar().showMessage(
            f"Bước {step['id']} | {step['action']} | {result.status} | {result.detail}"
        )

    @pyqtSlot(str)
    def _on_simulation_finished(self, message):
        self._set_state(UIState.READY if self.messages else UIState.EMPTY)
        self.statusBar().showMessage(message)

    @pyqtSlot()
    def _reset(self):
        if self.state in (UIState.RUNNING, UIState.PAUSED):
            self._clear_trace()
            self.reset_requested.emit()
            self._clear_run_display()
            self._set_state(UIState.READY)
            self.statusBar().showMessage("Đã reset mô phỏng. Giữ nguyên CSV đã nạp.")

    def closeEvent(self, event):
        self.controller.stop()
        super().closeEvent(event)

    def _clear_trace(self):
        self.trace_table.setRowCount(0)
        self.trace_count_label.setText("0 bản ghi")
        self.export_button.setEnabled(False)

    @pyqtSlot(dict)
    def _on_trace_recorded(self, record):
        self.append_trace(
            [
                self.trace_table.rowCount() + 1,
                record["timestamp"],
                record["step_id"],
                record["process"],
                record["action"],
                record["mechanism"],
                record["status"],
                f"{record['latency_ms']:.3f}",
                record["detail"],
            ]
        )

    def append_trace(self, values: list):
        """Điểm tích hợp dành cho bộ chạy; gọi trên UI thread bằng signal/slot."""
        if len(values) != len(self.TRACE_COLUMNS):
            raise ValueError("Một dòng trace phải có đủ 9 trường.")
        scrollbar = self.trace_table.verticalScrollBar()
        follow_latest = scrollbar.value() == scrollbar.maximum()
        row = self.trace_table.rowCount()
        self.trace_table.insertRow(row)
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setToolTip(str(value))
            self.trace_table.setItem(row, column, item)
        status_color = {
            "SUCCESS": "#14745b",
            "BLOCKED": "#9a6700",
            "TIMEOUT": "#9a6700",
            "ERROR": "#b42318",
        }.get(str(values[6]))
        if status_color:
            self.trace_table.item(row, 6).setForeground(QColor(status_color))
        self.trace_count_label.setText(f"{row + 1} bản ghi")
        self.export_button.setEnabled(True)
        if follow_latest:
            self.trace_table.scrollToBottom()

    @pyqtSlot()
    def _choose_export_path(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Xuất Trace CSV", "trace.csv", "CSV (*.csv)"
        )
        if path:
            self.export_trace(path)

    def export_trace(self, path: str | Path) -> bool:
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(self.TRACE_COLUMNS)
                for row in range(self.trace_table.rowCount()):
                    writer.writerow(
                        self.trace_table.item(row, col).text()
                        for col in range(self.trace_table.columnCount())
                    )
        except (OSError, UnicodeError, csv.Error) as error:
            self.statusBar().showMessage(f"Không thể xuất trace: {error}")
            return False
        self.statusBar().showMessage(f"Đã xuất trace: {path}")
        return True
