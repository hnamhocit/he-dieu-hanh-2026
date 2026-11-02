"""Nạp CSV, điều khiển bộ chạy IPC và hiển thị sự kiện Core trên UI thread."""

from __future__ import annotations

import csv
from dataclasses import asdict
from enum import Enum
from pathlib import Path
from time import perf_counter

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QAbstractScrollArea, QCheckBox, QComboBox, QFileDialog, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit,
    QMainWindow, QProgressBar, QPushButton, QScrollArea, QSpinBox,
    QSizePolicy, QStyle, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from src.gui.styles import STYLESHEET, TRACE_DEFAULT_COLORS, TRACE_STATUS_COLORS
from src.gui.simulation_controller import SimulationController
from src.gui.widgets import BufferChart, BufferSlots
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
            result = {"success": False, "error_code": "FILE_READ_ERROR",
                      "detail": str(error), "data": []}
        except csv.Error as error:
            result = {"success": False, "error_code": "INVALID_CSV",
                      "detail": str(error), "data": []}
        except ValueError as error:
            result = {"success": False, "error_code": "INVALID_DATA",
                      "detail": str(error), "data": []}
        else:
            result = {"success": True, "error_code": "OK", "detail": "",
                      "data": [asdict(step) for step in steps]}
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

    TRACE_COLUMNS = ("#", "Timestamp", "Step", "Process", "Action", "Mechanism",
                     "Status", "Latency (ms)", "Detail")

    def __init__(self):
        super().__init__()
        self.selected_path: Path | None = None
        self.messages: list[dict] = []
        self.state = UIState.EMPTY
        self._loader = None
        self.actor_labels = {}
        self._run_started = None
        self._paused_at = None
        self._pause_seconds = 0.0
        self._produced = self._consumed = self._failed = 0
        self.setWindowTitle("OS_IPC_09 - Desktop IPC Simulator")
        self.resize(1180, 980)
        self.setMinimumSize(940, 700)
        self.setStyleSheet(STYLESHEET)
        self._build_layout()
        self._set_state(UIState.EMPTY)

        self.controller = SimulationController(self)

        self.start_requested.connect(self.controller.start)
        self.pause_requested.connect(self.controller.pause)
        self.resume_requested.connect(self.controller.resume)
        self.reset_requested.connect(self.controller.reset)

        self.controller.step_completed.connect(self._on_step_completed)
        self.controller.finished.connect(self._on_simulation_finished)
        self.controller.frame_changed.connect(self._on_frame_changed)
        self.controller.trace_recorded.connect(self._on_trace_recorded)

        self.statusBar().clearMessage()

    def _build_layout(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.setCentralWidget(scroll)
        page = QWidget()
        page.setObjectName("page")
        scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)

        title = QFrame()
        title.setObjectName("titleBar")
        title_row = QHBoxLayout(title)
        title_row.addWidget(_label("▣  OS_IPC_09 - Desktop IPC Simulator", "appTitle"))
        title_row.addStretch()
        title_row.addWidget(_label("MÔ PHỎNG THEO CSV", "modeBadge"))
        layout.addWidget(title)

        top = QHBoxLayout()
        top.setSpacing(14)
        top.addWidget(self._build_csv_panel(), 1)
        top.addWidget(self._build_config_panel(), 1)
        layout.addLayout(top)
        layout.addWidget(self._build_buffer_panel(), 3)
        layout.addWidget(self._build_trace_panel(), 2)

    def _build_csv_panel(self):
        group = QGroupBox("▣  CSV Input")
        layout = QVBoxLayout(group)
        row = QHBoxLayout()
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        self.file_path.setPlaceholderText("Chưa chọn file…")
        self.file_path.setAccessibleName("Đường dẫn file CSV")
        self.browse_button = QPushButton("Chọn file")
        self.browse_button.setObjectName("browseButton")
        self.browse_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.check_button = QPushButton("Kiểm tra")
        self.check_button.setObjectName("checkButton")
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
        self.file_feedback = _label("")
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
        self.mechanism_combo.model().item(1).setEnabled(False)
        self.mechanism_combo.setItemData(1, "Pipe chưa có bộ chạy.", Qt.ItemDataRole.ToolTipRole)
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(1, 1024)
        self.buffer_spin.setValue(5)
        self.producer_spin = QSpinBox()
        self.producer_spin.setRange(0, 64)
        self.consumer_spin = QSpinBox()
        self.consumer_spin.setRange(0, 64)
        for widget in (self.producer_spin, self.consumer_spin):
            widget.setToolTip("Danh tính và số lượng tiến trình lấy từ CSV; bộ chạy không tạo OS process.")
        for label, widget, row, column in (
            ("Cơ chế IPC", self.mechanism_combo, 0, 0),
            ("Số Producer trong CSV", self.producer_spin, 0, 1),
            ("Dung lượng Buffer", self.buffer_spin, 2, 0),
            ("Số Consumer trong CSV", self.consumer_spin, 2, 1),
        ):
            text = _label(label)
            text.setBuddy(widget)
            grid.addWidget(text, row, column)
            grid.addWidget(widget, row + 1, column)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        self.priority_checkbox = QCheckBox("Chế độ hàng đợi ưu tiên (Priority Queue)")
        self.priority_checkbox.setObjectName("priorityCheckBox")
        self.priority_checkbox.setEnabled(False)
        self.priority_checkbox.setToolTip("Chỉ kích hoạt khi chọn cơ chế Message Queue")
        layout.addWidget(self.priority_checkbox)
        self.mechanism_combo.currentIndexChanged.connect(self._on_mechanism_changed)
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
        self.control_state_label = _label("")
        self.buffer_spin.valueChanged.connect(self._capacity_changed)
        return group

    def _actor_card(self, title, name, counter_labels):
        card = QFrame()
        card.setObjectName(name)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(_label(title, "cardTitle"))
        labels = []
        for text in counter_labels:
            label = _label(text)
            layout.addWidget(label)
            labels.append(label)
        badge = _label("Sẵn sàng", "readyBadge")
        layout.addWidget(badge, alignment=Qt.AlignmentFlag.AlignLeft)
        self.actor_labels[name] = (labels, badge)
        return card

    def _build_buffer_panel(self):
        group = QGroupBox("▥  Buffer Visualization")
        group.setObjectName("bufferGroup")
        layout = QVBoxLayout(group)
        actors = QHBoxLayout()
        actors.setSpacing(14)
        actors.addWidget(self._actor_card("◉  Producer", "producerCard",
                                         ("Tiến trình: —", "Đã ghi: 0")), 2)
        actors.addWidget(_label("➔", "arrow"), 0, Qt.AlignmentFlag.AlignCenter)
        buffer_card = QFrame()
        buffer_card.setObjectName("bufferCard")
        buffer_layout = QVBoxLayout(buffer_card)
        buffer_layout.setContentsMargins(8, 6, 8, 6)
        buffer_layout.setSpacing(2)
        buffer_layout.addWidget(_label("▤  Shared Buffer / Message Queue", "cardTitle"))
        self.buffer_slots = BufferSlots()
        buffer_layout.addWidget(self.buffer_slots)
        legend = _label("Xám: Trống · Vàng: Đang khóa · Tím: Đang ghi · Xanh lá: Đã ghi · Xanh dương: Đang đọc")
        legend.setWordWrap(True)
        buffer_layout.addWidget(legend)
        self.sync_state_label = _label("Mutex: Mở · Empty: 5 · Full: 0 · IN: 0 · OUT: 0")
        self.sync_state_label.setWordWrap(True)
        buffer_layout.addWidget(self.sync_state_label)
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
        actors.addWidget(buffer_card, 6)
        actors.addWidget(_label("➔", "arrow"), 0, Qt.AlignmentFlag.AlignCenter)
        actors.addWidget(self._actor_card("◉  Consumer", "consumerCard",
                                         ("Tiến trình: —", "Đã đọc: 0")), 2)
        layout.addLayout(actors)

        lower = QHBoxLayout()
        lower.setSpacing(14)
        chart = QFrame()
        chart.setObjectName("chartCard")
        chart_layout = QVBoxLayout(chart)
        chart_layout.addWidget(_label("▥  Mức sử dụng Buffer theo thời gian", "cardTitle"))
        self.buffer_chart = BufferChart()
        chart_layout.addWidget(self.buffer_chart)
        lower.addWidget(chart, 7)
        stats = QFrame()
        stats.setObjectName("statsCard")
        stats_layout = QVBoxLayout(stats)
        stats_layout.addWidget(_label("Thống kê nhanh", "cardTitle"))
        stats_form = QFormLayout()
        self.total_steps_label = _label("0", "statTotal")
        stats_form.addRow("Tổng số bước:", self.total_steps_label)
        self.processed_steps_label = _label("0", "statProcessed")
        self.failed_steps_label = _label("0", "statFailed")
        self.throughput_label = _label("0", "statThroughput")
        stats_form.addRow("Đã xử lý:", self.processed_steps_label)
        stats_form.addRow("Bị chặn / lỗi:", self.failed_steps_label)
        stats_form.addRow("Thông lượng (msg/s):", self.throughput_label)
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
        self.trace_table.setAlternatingRowColors(False)
        self.trace_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.trace_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.trace_table.setMinimumHeight(110)
        self.trace_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Ignored)
        self.trace_table.setSizeAdjustPolicy(QAbstractScrollArea.SizeAdjustPolicy.AdjustIgnored)
        header = self.trace_table.horizontalHeader()
        header.setDefaultSectionSize(100)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.Stretch)
        self.trace_table.setColumnWidth(0, 36)
        self.trace_table.setColumnWidth(1, 155)
        layout.addWidget(self.trace_table)
        row = QHBoxLayout()
        legend = _label("Xanh: SUCCESS · Vàng: BLOCKED · Cam: TIMEOUT · Đỏ: ERROR")
        legend.setWordWrap(True)
        row.addWidget(legend, 1)
        self.export_button = QPushButton("Xuất Trace CSV")
        self.export_button.setObjectName("exportButton")
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
        self.controller.reset()
        self._clear_run_display()
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
        self.file_feedback.setText("")
        self._set_state(UIState.SELECTED)

    @pyqtSlot()
    def validate_csv(self):
        if self.selected_path is None or self.state not in (UIState.SELECTED, UIState.READY):
            return
        self.messages = []
        self.controller.reset()
        self._clear_run_display()
        self.trace_table.setRowCount(0)
        self.export_button.setEnabled(False)
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
        for widget, actions in (
            (self.producer_spin, {"PRODUCE", "SEND"}),
            (self.consumer_spin, {"CONSUME", "RECEIVE"}),
        ):
            count = len({step["sender"] for step in self.messages if step["action"] in actions})
            widget.setRange(0, max(64, count))
            widget.setValue(count)
        self.row_count_label.setText(str(len(self.messages)))
        self.total_steps_label.setText(str(len(self.messages)))
        self.file_feedback.setStyleSheet("color: #15803d; font-weight: 600;")
        self.file_feedback.setText("CSV hợp lệ")
        self._set_state(UIState.READY)

    def configuration(self) -> dict:
        return {"mechanism": self.mechanism_combo.currentData(),
                "buffer_capacity": self.buffer_spin.value(),
                "producer_count": self.producer_spin.value(),
                "consumer_count": self.consumer_spin.value(),
                "is_priority": self.priority_checkbox.isChecked()}

    def _on_mechanism_changed(self):
        is_mq = self.mechanism_combo.currentData() == "MESSAGE_QUEUE"
        editable = self.state in (UIState.EMPTY, UIState.SELECTED, UIState.READY)
        self.priority_checkbox.setEnabled(editable and is_mq)
        if not is_mq:
            self.priority_checkbox.setChecked(False)

    def _set_state(self, state: UIState):
        self.state = state
        editable = state in (UIState.EMPTY, UIState.SELECTED, UIState.READY)
        self.browse_button.setEnabled(editable)
        self.check_button.setEnabled(state in (UIState.SELECTED, UIState.READY))
        for widget in (self.mechanism_combo, self.buffer_spin):
            widget.setEnabled(editable)
        is_mq = self.mechanism_combo.currentData() == "MESSAGE_QUEUE"
        self.priority_checkbox.setEnabled(editable and is_mq)
        self.producer_spin.setEnabled(False)
        self.consumer_spin.setEnabled(False)
        self.start_button.setEnabled(state in (UIState.READY, UIState.PAUSED))
        self.start_button.setText("Tiếp tục" if state == UIState.PAUSED else "Start")
        self.pause_button.setEnabled(state == UIState.RUNNING)
        self.reset_button.setEnabled(
            state in (UIState.READY, UIState.RUNNING, UIState.PAUSED)
        )
        self.file_state_label.setText("Hợp lệ" if self.messages else state.value)
        self.control_state_label.setText(state.value)

    @pyqtSlot(int)
    def _capacity_changed(self, capacity):
        self.buffer_slots.set_capacity(capacity)
        self.buffer_count_label.setText(f"Đang chứa: 0 / {capacity}")
        self.buffer_progress.setRange(0, capacity)
        self.buffer_progress.setValue(0)
        self.buffer_percent_label.setText("0%")
        self.sync_state_label.setText(
            f"Mutex: Mở · Empty: {capacity} · Full: 0 · IN: 0 · OUT: 0"
        )

    def _clear_run_display(self):
        self._capacity_changed(self.buffer_spin.value())
        self.buffer_chart.reset()
        self._run_started = self._paused_at = None
        self._pause_seconds = 0.0
        self._produced = self._consumed = self._failed = 0
        for label in (self.processed_steps_label, self.failed_steps_label, self.throughput_label):
            label.setText("0")
        self._update_actors()
        if not self.messages:
            self.producer_spin.setValue(0)
            self.consumer_spin.setValue(0)

    def _elapsed(self):
        if self._run_started is None:
            return 0.0
        end = self._paused_at if self._paused_at is not None else perf_counter()
        return max(0.0, end - self._run_started - self._pause_seconds)

    def _update_actors(self, step=None, phase=None):
        sending = step is not None and step["action"] in ("PRODUCE", "SEND")
        for name, total, active in (
            ("producerCard", self._produced, step is not None and sending),
            ("consumerCard", self._consumed, step is not None and not sending),
        ):
            labels, badge = self.actor_labels[name]
            labels[0].setText(f"Tiến trình: {step['sender']}" if active else "Tiến trình: —")
            labels[1].setText(f"Đã ghi: {total}" if name == "producerCard" else f"Đã đọc: {total}")
            badge.setText(BufferSlots.LABELS.get(phase, "Sẵn sàng") if active else "Sẵn sàng")

    def _show_snapshot(self, snapshot):
        count, capacity = snapshot["count"], snapshot["capacity"]
        self.buffer_count_label.setText(f"Đang chứa: {count} / {capacity}")
        self.buffer_progress.setRange(0, capacity)
        self.buffer_progress.setValue(count)
        self.buffer_percent_label.setText(f"{count * 100 // capacity}%")
        if self.controller.mechanism_name == "SHARED_MEMORY":
            holder = snapshot.get("mutex_holder")
            mutex = f"Khóa bởi {holder}" if snapshot["mutex"] == 0 else "Mở"
            self.sync_state_label.setText(
                f"Mutex: {mutex} · Empty: {snapshot['empty']} · Full: {snapshot['full']}"
                f" · IN: {snapshot['in_ptr']} · OUT: {snapshot['out_ptr']}"
            )
        else:
            self.sync_state_label.setText(
                f"Queue: {snapshot.get('queue_type', 'FIFO')} · Empty: {snapshot['empty']}"
                f" · Full: {snapshot['full']}"
            )

    @pyqtSlot(dict)
    def _on_frame_changed(self, frame):
        self.buffer_slots.set_frame(frame)
        self._show_snapshot(frame["snapshot"])
        self._update_actors(frame["step"], frame["phase"])
        self.statusBar().showMessage(
            f"Phát lại bước {frame['step']['id']} · {frame['process_id']} · "
            f"Ô {frame['slot_index']}: {BufferSlots.LABELS[frame['phase']]}"
        )

    @pyqtSlot(dict)
    def _on_trace_recorded(self, trace):
        self.append_trace([
            self.trace_table.rowCount() + 1, trace["timestamp"], trace["step_id"],
            trace["process"], trace["action"], trace["mechanism"], trace["status"],
            f"{trace['latency_ms']:.3f}", trace["detail"],
        ])
        if trace["status"] != "SUCCESS":
            self._failed += 1
            self.failed_steps_label.setText(str(self._failed))

    @pyqtSlot()
    def _start(self):
        if self.state not in (UIState.READY, UIState.PAUSED):
            return

        resuming = self.state == UIState.PAUSED
        self._set_state(UIState.RUNNING)
        self.statusBar().clearMessage()

        if resuming:
            if self._paused_at is not None:
                self._pause_seconds += perf_counter() - self._paused_at
                self._paused_at = None
            self.resume_requested.emit()
        else:
            # Lần chạy mới: xóa trạng thái hiển thị cũ.
            self._clear_run_display()
            self._run_started = perf_counter()
            self.buffer_chart.add_sample(0.0, 0, self.buffer_spin.value())
            self.trace_table.setRowCount(0)
            self.export_button.setEnabled(False)

            self.start_requested.emit(
                self.messages,
                self.configuration(),
            )

    @pyqtSlot()
    def _pause(self):
        if self.state == UIState.RUNNING:
            self._paused_at = perf_counter()
            self._set_state(UIState.PAUSED)
            self.pause_requested.emit()
            self.statusBar().clearMessage()

    @pyqtSlot()
    def _reset(self):
        if self.state not in (
            UIState.READY,
            UIState.RUNNING,
            UIState.PAUSED,
        ):
            return

        # Dừng timer và xóa dữ liệu trong controller.
        self.reset_requested.emit()

        # Xóa dữ liệu đang hiển thị.
        self._clear_run_display()
        self.trace_table.setRowCount(0)
        self.export_button.setEnabled(False)

        self._set_state(UIState.READY)
        self.statusBar().clearMessage()

    @pyqtSlot(dict)
    def _on_step_completed(self, event):
        snapshot = event["snapshot"]
        step = event["step"]
        result = event["result"]

        # Đưa dữ liệu từ Core vào các ô nhớ.
        self.buffer_slots.set_snapshot(snapshot)
        self._show_snapshot(snapshot)

        count = snapshot["count"]
        capacity = snapshot["capacity"]

        # Hiển thị tiến độ thực hiện CSV.
        self.control_state_label.setText(
            f"Đang chạy: {event['completed']}/{event['total']} bước"
        )
        self.processed_steps_label.setText(str(event["completed"]))
        if result.success:
            if step["action"] in ("PRODUCE", "SEND"):
                self._produced += 1
            else:
                self._consumed += 1
        self._update_actors()
        elapsed = self._elapsed()
        self.buffer_chart.add_sample(elapsed, count, capacity)
        self.throughput_label.setText(f"{self._produced / max(elapsed, 0.001):.2f}")

        self.statusBar().showMessage(
            f"Bước {step['id']} | {step['action']} | "
            f"{result.status} | {result.detail}"
        )

    @pyqtSlot(str)
    def _on_simulation_finished(self, message):
        self._update_actors()
        self._set_state(UIState.READY)
        if any(keyword in message.lower() for keyword in ("lỗi", "error", "không thể", "thất bại")):
            self.statusBar().showMessage(message)
        else:
            self.statusBar().clearMessage()

    def closeEvent(self, event):
        self.controller.reset()
        super().closeEvent(event)

    def append_trace(self, values: list):
        """Điểm tích hợp dành cho bộ chạy; gọi trên UI thread bằng signal/slot."""
        if len(values) != len(self.TRACE_COLUMNS):
            raise ValueError("Một dòng trace phải có đủ 9 trường.")
        scrollbar = self.trace_table.verticalScrollBar()
        follow_tail = scrollbar.value() >= scrollbar.maximum() - 1
        status = str(values[6]).strip().upper()
        background, foreground = TRACE_STATUS_COLORS.get(status, TRACE_DEFAULT_COLORS)
        row = self.trace_table.rowCount()
        self.trace_table.insertRow(row)
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            item.setBackground(QColor(background))
            item.setForeground(QColor(foreground))
            item.setToolTip(str(value))
            self.trace_table.setItem(row, column, item)
        if follow_tail:
            self.trace_table.scrollToBottom()
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
