"""Layout HDH-31: nạp CSV, cấu hình, điều khiển, vùng Buffer và Trace Log.

Đây là giao diện chuẩn bị tích hợp bộ chạy IPC. Các nút phát signals;
không thực thi thuật toán hoặc sinh số liệu mô phỏng trong GUI.
"""

from __future__ import annotations

import csv
from enum import Enum
from pathlib import Path

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal, pyqtSlot
from PyQt6.QtWidgets import (
    QAbstractItemView, QAbstractScrollArea, QComboBox, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QProgressBar, QPushButton, QScrollArea, QSpinBox,
    QStyle, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.gui.styles import STYLESHEET
from src.gui.widgets import BufferChart, BufferSlots
from src.utils.csv_reader import read_messages


class UIState(str, Enum):
    EMPTY = "Chưa chọn file"
    SELECTED = "Chưa kiểm tra"
    LOADING = "Đang kiểm tra"
    READY = "Sẵn sàng"
    RUNNING = "Đã yêu cầu Start"
    PAUSED = "Đã yêu cầu Pause"


class _LoadSignals(QObject):
    finished = pyqtSignal(object)


class _CSVLoader(QRunnable):
    def __init__(self, path: Path):
        super().__init__()
        self.path = path
        self.signals = _LoadSignals()

    @pyqtSlot()
    def run(self):
        self.signals.finished.emit(read_messages(self.path))


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

    TRACE_COLUMNS = ("#", "Timestamp", "Step", "Process", "Action", "Mechanism",
                     "Status", "Latency (ms)", "Detail")

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
        self._set_state(UIState.EMPTY)
        self.statusBar().showMessage("Chọn file CSV → Kiểm tra → Start. Chế độ dựng giao diện.")

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
        title_row.addWidget(_label("CHẾ ĐỘ GIAO DIỆN", "modeBadge"))
        layout.addWidget(title)

        top = QHBoxLayout()
        top.setSpacing(12)
        top.addWidget(self._build_csv_panel(), 1)
        top.addWidget(self._build_config_panel(), 1)
        layout.addLayout(top)
        layout.addWidget(self._build_buffer_panel(), 3)
        layout.addWidget(self._build_trace_panel(), 2)
        layout.addWidget(_label(
            "① Chọn file CSV    →    ② Kiểm tra & cấu hình    →    ③ Start / Pause / Reset"
            "    →    ④ Theo dõi Buffer & Log    →    ⑤ Xuất Trace CSV", "flow"
        ))

    def _build_csv_panel(self):
        group = QGroupBox("▣  CSV Input")
        layout = QVBoxLayout(group)
        row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        self.file_path.setPlaceholderText("Chưa chọn file…")
        self.file_path.setAccessibleName("Đường dẫn file CSV")
        self.browse_button = QPushButton("Chọn file")
        self.browse_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.check_button = QPushButton("Kiểm tra")
        self.check_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton))
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
        for title, value in (("Shared Memory", "SHARED_MEMORY"),
                             ("Pipe", "PIPE"), ("Message Queue", "MESSAGE_QUEUE")):
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
        self.start_button = QPushButton("Start")
        self.pause_button = QPushButton("Pause")
        self.reset_button = QPushButton("Reset")
        self.start_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay))
        self.pause_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPause))
        self.reset_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_BrowserReload))
        for button, name, callback in (
            (self.start_button, "startButton", self._start),
            (self.pause_button, "pauseButton", self._pause),
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
        actors.addWidget(self._actor_card("◉  Producer", "producerCard",
                                         ("Đang gửi:     0", "Đã gửi:         0")), 3)
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
        progress_row.addWidget(_label("0%"))
        buffer_layout.addLayout(progress_row)
        actors.addWidget(buffer_card, 4)
        actors.addWidget(_label("→", "arrow"))
        actors.addWidget(self._actor_card("◉  Consumer", "consumerCard",
                                         ("Đã nhận:       0", "Đã xử lý:       0")), 3)
        layout.addLayout(actors)

        lower = QHBoxLayout()
        chart = QFrame()
        chart.setObjectName("chartCard")
        chart_layout = QVBoxLayout(chart)
        chart_layout.addWidget(_label("▥  Mức sử dụng Buffer theo thời gian", "cardTitle"))
        chart_layout.addWidget(BufferChart())
        lower.addWidget(chart, 7)
        stats = QFrame()
        stats.setObjectName("statsCard")
        stats_layout = QVBoxLayout(stats)
        stats_layout.addWidget(_label("Thống kê nhanh", "cardTitle"))
        stats_form = QFormLayout()
        self.total_steps_label = _label("0")
        stats_form.addRow("Tổng số bước", self.total_steps_label)
        stats_form.addRow("Đã xử lý", _label("0"))
        stats_form.addRow("Lỗi mô phỏng", _label("0"))
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
        self.trace_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.trace_table.setMinimumHeight(110)
        self.trace_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustToContents)
        header = self.trace_table.horizontalHeader()
        header.setDefaultSectionSize(100)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.trace_table.setColumnWidth(0, 36)
        self.trace_table.setColumnWidth(1, 155)
        layout.addWidget(self.trace_table)
        row = QHBoxLayout()
        row.addWidget(_label("Log sẽ xuất hiện khi kết nối bộ chạy IPC."))
        row.addStretch()
        self.export_button = QPushButton("Xuất Trace CSV")
        self.export_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self._choose_export_path)
        row.addWidget(self.export_button)
        layout.addLayout(row)
        return group

    @pyqtSlot()
    def _choose_file(self):
        directory = Path(__file__).resolve().parents[2] / "data" / "input"
        path, _ = QFileDialog.getOpenFileName(self, "Chọn file CSV", str(directory), "CSV (*.csv)")
        if path:
            self.select_csv(path)

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
        self.trace_table.setRowCount(0)
        self.export_button.setEnabled(False)
        try:
            self.file_size_label.setText(f"{self.selected_path.stat().st_size / 1024:.2f} KB")
        except OSError:
            self.file_size_label.setText("Không xác định")
        self.file_feedback.setStyleSheet("")
        self.file_feedback.setText("Nhấn Kiểm tra để xác nhận dữ liệu CSV.")
        self._set_state(UIState.SELECTED)

    @pyqtSlot()
    def validate_csv(self):
        if self.selected_path is None or self.state not in (UIState.SELECTED, UIState.READY):
            return
        self.messages = []
        self.row_count_label.setText("0")
        self.total_steps_label.setText("0")
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
        self.file_feedback.setText("CSV hợp lệ. Có thể cấu hình và thử các nút điều khiển.")
        self._set_state(UIState.READY)

    def configuration(self) -> dict:
        return {"mechanism": self.mechanism_combo.currentData(),
                "buffer_capacity": self.buffer_spin.value(),
                "producer_count": self.producer_spin.value(),
                "consumer_count": self.consumer_spin.value()}

    def _set_state(self, state: UIState):
        self.state = state
        editable = state in (UIState.EMPTY, UIState.SELECTED, UIState.READY)
        self.browse_button.setEnabled(editable)
        self.check_button.setEnabled(state in (UIState.SELECTED, UIState.READY))
        for widget in (self.mechanism_combo, self.buffer_spin, self.producer_spin, self.consumer_spin):
            widget.setEnabled(editable)
        self.start_button.setEnabled(state in (UIState.READY, UIState.PAUSED))
        self.start_button.setText("Tiếp tục" if state == UIState.PAUSED else "Start")
        self.pause_button.setEnabled(state == UIState.RUNNING)
        self.reset_button.setEnabled(state in (UIState.RUNNING, UIState.PAUSED))
        self.file_state_label.setText("Hợp lệ" if self.messages else state.value)
        self.control_state_label.setText(state.value)

    @pyqtSlot(int)
    def _capacity_changed(self, capacity):
        self.buffer_slots.set_capacity(capacity)
        self.buffer_count_label.setText(f"Đang chứa: 0 / {capacity}")
        self.buffer_progress.setRange(0, capacity)

    @pyqtSlot()
    def _start(self):
        if self.state not in (UIState.READY, UIState.PAUSED):
            return
        resuming = self.state == UIState.PAUSED
        self._set_state(UIState.RUNNING)
        if resuming:
            self.resume_requested.emit()
        else:
            self.start_requested.emit(self.messages, self.configuration())
        self.statusBar().showMessage("Đã gửi yêu cầu điều khiển. Chế độ giao diện chưa thực thi IPC.")

    @pyqtSlot()
    def _pause(self):
        if self.state == UIState.RUNNING:
            self._set_state(UIState.PAUSED)
            self.pause_requested.emit()

    @pyqtSlot()
    def _reset(self):
        if self.state in (UIState.RUNNING, UIState.PAUSED):
            self.trace_table.setRowCount(0)
            self.export_button.setEnabled(False)
            self._set_state(UIState.READY)
            self.reset_requested.emit()
            self.statusBar().showMessage("Đã reset trạng thái điều khiển. Giữ nguyên CSV đã nạp.")

    def append_trace(self, values: list):
        """Điểm tích hợp dành cho bộ chạy; gọi trên UI thread bằng signal/slot."""
        if len(values) != len(self.TRACE_COLUMNS):
            raise ValueError("Một dòng trace phải có đủ 9 trường.")
        row = self.trace_table.rowCount()
        self.trace_table.insertRow(row)
        for column, value in enumerate(values):
            self.trace_table.setItem(row, column, QTableWidgetItem(str(value)))
        self.export_button.setEnabled(True)

    @pyqtSlot()
    def _choose_export_path(self):
        path, _ = QFileDialog.getSaveFileName(self, "Xuất Trace CSV", "trace.csv", "CSV (*.csv)")
        if path:
            self.export_trace(path)

    def export_trace(self, path: str | Path) -> bool:
        try:
            with open(path, "w", encoding="utf-8-sig", newline="") as stream:
                writer = csv.writer(stream)
                writer.writerow(self.TRACE_COLUMNS)
                for row in range(self.trace_table.rowCount()):
                    writer.writerow(self.trace_table.item(row, col).text()
                                    for col in range(self.trace_table.columnCount()))
        except (OSError, UnicodeError, csv.Error) as error:
            self.statusBar().showMessage(f"Không thể xuất trace: {error}")
            return False
        self.statusBar().showMessage(f"Đã xuất trace: {path}")
        return True
