"""Tab benchmark: worker chỉ đo Core, widget và biểu đồ cập nhật trên UI thread."""

from threading import Event

from PyQt6.QtCore import QObject, QRunnable, QThreadPool, Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QProgressBar, QScrollArea,
    QPushButton, QSpinBox, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator

from src.core.benchmark import BenchmarkCancelled, BenchmarkConfig, run_benchmark


NAMES = {"SHARED_MEMORY": "Shared Memory", "MESSAGE_QUEUE": "Message Queue"}
COLORS = {"SHARED_MEMORY": "#2563eb", "MESSAGE_QUEUE": "#0d9488"}

BENCHMARK_STYLE = """
QWidget#benchmarkPage { background: #f1f5f9; }
QFrame#benchmarkCard { background: white; border: 1px solid #e2e8f0; border-radius: 12px; }
QLabel#benchmarkTitle { font-size: 24px; font-weight: 700; color: #0f172a; }
QLabel#benchmarkSubtitle { color: #64748b; font-size: 12px; }
QLabel#benchmarkSection { font-size: 14px; font-weight: 700; color: #0f172a; }
QLabel#benchmarkEyebrow { color: #2563eb; font-size: 10px; font-weight: 700; }
QLabel#benchmarkMetric { font-size: 25px; font-weight: 700; color: #0f172a; }
QLabel#benchmarkMuted { color: #64748b; font-size: 11px; }
QLabel#benchmarkBadge { color: #0f766e; background: #ccfbf1; border-radius: 10px; padding: 5px 12px; font-weight: 700; }
QPushButton#benchmarkRun { background: #2563eb; color: white; border: none; border-radius: 7px; padding: 10px; font-weight: 700; }
QPushButton#benchmarkRun:hover { background: #1d4ed8; }
QPushButton#benchmarkRun:disabled { background: #cbd5e1; color: #f8fafc; }
QPushButton#benchmarkCancel { border: 1px solid #e2e8f0; border-radius: 7px; padding: 8px; background: white; }
QPushButton#benchmarkCancel:disabled { color: #94a3b8; background: #f8fafc; }
QComboBox, QSpinBox { min-height: 24px; border: 1px solid #cbd5e1; border-radius: 6px; background: #f8fafc; padding: 5px 8px; }
QTableWidget { border: none; border-radius: 0; gridline-color: #f1f5f9; }
QHeaderView::section { background: #f8fafc; border: none; border-bottom: 1px solid #e2e8f0; padding: 10px 4px; color: #64748b; font-size: 10px; }
"""


class _Signals(QObject):
    result = pyqtSignal(object)
    finished = pyqtSignal(str)


class _Worker(QRunnable):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.cancel = Event()
        self.signals = _Signals()

    @pyqtSlot()
    def run(self):
        try:
            run_benchmark(self.config, self.cancel, self.signals.result.emit)
        except BenchmarkCancelled:
            message = "Đã dừng. Bảng giữ các lần chạy đã hoàn tất."
        except Exception as error:
            message = f"Benchmark thất bại: {error}"
        else:
            message = "Benchmark hoàn tất."
        self.signals.finished.emit(message)


class BenchmarkTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.worker = None
        self.results = []
        self.setStyleSheet(BENCHMARK_STYLE)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)
        page = QWidget()
        page.setObjectName("benchmarkPage")
        scroll.setWidget(page)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(18)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(5)
        titles.addWidget(self._label("PERFORMANCE LAB", "benchmarkEyebrow"))
        titles.addWidget(self._label("Benchmark & Analysis", "benchmarkTitle"))
        titles.addWidget(self._label("Đo hiệu năng, đối chiếu hai cơ chế IPC trên cùng cấu hình.", "benchmarkSubtitle"))
        header.addLayout(titles)
        header.addStretch()
        self.badge = self._label("SẴN SÀNG", "benchmarkBadge")
        header.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)
        body = QHBoxLayout()
        body.setSpacing(18)
        layout.addLayout(body, 1)
        sidebar, settings = self._card()
        sidebar.setFixedWidth(240)
        body.addWidget(sidebar, 0, Qt.AlignmentFlag.AlignTop)
        settings.addWidget(self._label("Cấu hình phép đo", "benchmarkSection"))
        settings.addWidget(self._label("Không cần nạp file CSV.", "benchmarkMuted"))
        self.mechanism_combo = QComboBox()
        self.mechanism_combo.addItem("So sánh cả hai", ("SHARED_MEMORY", "MESSAGE_QUEUE"))
        for key, name in NAMES.items():
            self.mechanism_combo.addItem(name, (key,))
        self.message_spin = self._spin(1, 100000, 1000)
        self.capacity_spin = self._spin(1, 1024, 16)
        self.repeats_spin = self._spin(1, 10, 3)
        for title, widget in (("Cơ chế IPC", self.mechanism_combo),
                              ("Số thông điệp / lần", self.message_spin),
                              ("Dung lượng buffer", self.capacity_spin),
                              ("Số lần chạy / cơ chế", self.repeats_spin)):
            settings.addSpacing(6)
            settings.addWidget(self._label(title, "benchmarkMuted"))
            settings.addWidget(widget)
        settings.addSpacing(12)
        self.run_button = QPushButton("Chạy benchmark")
        self.run_button.setObjectName("benchmarkRun")
        self.cancel_button = QPushButton("Dừng benchmark")
        self.cancel_button.setObjectName("benchmarkCancel")
        self.cancel_button.setEnabled(False)
        settings.addWidget(self.run_button)
        settings.addWidget(self.cancel_button)
        settings.addSpacing(12)
        settings.addWidget(self._label("PHƯƠNG PHÁP ĐO", "benchmarkEyebrow"))
        note = self._label(
            "Gửi và nhận theo lô FIFO trong một luồng nền, có ghi trace. "
            "Latency bao gồm thời gian chờ trong buffer. Không tạo OS process.",
            "benchmarkMuted",
        )
        note.setWordWrap(True)
        settings.addWidget(note)
        dashboard = QVBoxLayout()
        dashboard.setSpacing(14)
        body.addLayout(dashboard, 1)
        metrics = QHBoxLayout()
        metrics.setSpacing(12)
        self.metric_labels = []
        self.metric_hints = []
        for title, hint in (("THROUGHPUT", "msg/s · lần đo mới nhất"),
                            ("LATENCY TRUNG BÌNH", "ms · lần đo mới nhất"),
                            ("TIẾN ĐỘ", "lần đo đã hoàn tất")):
            card, content = self._card()
            content.setSpacing(6)
            content.addWidget(self._label(title, "benchmarkMuted"))
            value = self._label("—", "benchmarkMetric")
            self.metric_labels.append(value)
            content.addWidget(value)
            hint_label = self._label(hint, "benchmarkMuted")
            hint_label.setWordWrap(True)
            self.metric_hints.append(hint_label)
            content.addWidget(hint_label)
            metrics.addWidget(card, 1)
        dashboard.addLayout(metrics)
        chart_card, chart_layout = self._card()
        chart_layout.addWidget(self._label("So sánh hiệu năng", "benchmarkSection"))
        legend = QHBoxLayout()
        for mechanism, name in NAMES.items():
            label = self._label(f"● {name}", "benchmarkMuted")
            label.setStyleSheet(f"color: {COLORS[mechanism]};")
            legend.addWidget(label)
        legend.addStretch()
        chart_layout.addLayout(legend)
        dashboard.addWidget(chart_card, 3)
        self.figure = Figure(figsize=(9, 3), facecolor="white")
        self.figure.subplots_adjust(left=0.15, right=0.97, bottom=0.20, top=0.83, wspace=0.60)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setMinimumSize(450, 240)
        self.throughput_axes, self.latency_axes = self.figure.subplots(1, 2)
        chart_layout.addWidget(self.canvas, 1)
        table_card, table_layout = self._card()
        table_layout.addWidget(self._label("Chi tiết từng lần chạy", "benchmarkSection"))
        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels([
            "Cơ chế", "Lần", "Tin nhận", "Giây", "msg/s",
            "TB (ms)", "Min (ms)", "Max (ms)",
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setMinimumHeight(160)
        table_layout.addWidget(self.table)
        dashboard.addWidget(table_card, 2)
        footer = QHBoxLayout()
        self.status_label = self._label("Sẵn sàng. Chọn cấu hình và bắt đầu phép đo.", "benchmarkMuted")
        self.status_label.setWordWrap(True)
        footer.addWidget(self.status_label, 1)
        self.progress.setFixedWidth(150)
        footer.addWidget(self.progress)
        dashboard.addLayout(footer)
        self._plot()
        self.run_button.clicked.connect(self.start)
        self.cancel_button.clicked.connect(self.cancel)

    @staticmethod
    def _label(text, name):
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setObjectName(name)
        return label

    @staticmethod
    def _card():
        card = QFrame()
        card.setObjectName("benchmarkCard")
        content = QVBoxLayout(card)
        content.setContentsMargins(16, 16, 16, 16)
        content.setSpacing(10)
        return card, content

    @staticmethod
    def _spin(minimum, maximum, value):
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setValue(value)
        return spin

    def start(self):
        if self.worker is not None:
            return
        config = BenchmarkConfig(
            self.mechanism_combo.currentData(), self.message_spin.value(),
            self.capacity_spin.value(), self.repeats_spin.value(),
        )
        self.results.clear()
        for label in self.metric_labels:
            label.setText("—")
        self.metric_hints[0].setText("msg/s · lần đo mới nhất")
        self.metric_hints[1].setText("ms · lần đo mới nhất")
        self.table.setRowCount(0)
        self._plot()
        self.progress.setRange(0, len(config.mechanisms) * config.repeats)
        self.progress.setValue(0)
        self.metric_labels[2].setText(f"0 / {self.progress.maximum()}")
        self._set_running(True)
        self.status_label.setText("Đang chạy benchmark…")
        self.worker = _Worker(config)
        self.worker.signals.result.connect(self._add_result)
        self.worker.signals.finished.connect(self._finished)
        QThreadPool.globalInstance().start(self.worker)

    def cancel(self):
        if self.worker is not None:
            self.worker.cancel.set()
            self.cancel_button.setEnabled(False)
            self.status_label.setText("Đang dừng benchmark…")

    def _set_running(self, running):
        self.badge.setText("ĐANG CHẠY" if running else "SẴN SÀNG")
        for widget in (self.run_button, self.mechanism_combo, self.message_spin,
                       self.capacity_spin, self.repeats_spin):
            widget.setEnabled(not running)
        self.cancel_button.setEnabled(running)

    @pyqtSlot(object)
    def _add_result(self, result):
        self.results.append(result)
        row = self.table.rowCount()
        self.table.insertRow(row)
        values = [NAMES[result.mechanism], result.run, result.message_count,
                  f"{result.elapsed_seconds:.4f}", f"{result.throughput:.2f}",
                  f"{result.latency_avg_ms:.4f}", f"{result.latency_min_ms:.4f}",
                  f"{result.latency_max_ms:.4f}"]
        for column, value in enumerate(values):
            item = QTableWidgetItem(str(value))
            if column == 0:
                item.setForeground(QColor(COLORS[result.mechanism]))
            else:
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self.table.setItem(row, column, item)
        self.progress.setValue(len(self.results))
        self.metric_labels[0].setText(f"{result.throughput:,.0f}")
        self.metric_labels[1].setText(f"{result.latency_avg_ms:.3f}")
        self.metric_labels[2].setText(f"{len(self.results)} / {self.progress.maximum()}")
        source = f"{NAMES[result.mechanism]} · lần {result.run}"
        self.metric_hints[0].setText(f"msg/s · {source}")
        self.metric_hints[1].setText(f"ms · {source}")
        self.table.scrollToBottom()
        self._plot()

    def _plot(self):
        for axes, field, title, unit in (
            (self.throughput_axes, "throughput", "Throughput", "msg/s"),
            (self.latency_axes, "latency_avg_ms", "Average latency", "ms"),
        ):
            axes.clear()
            axes.set_title(title, loc="left", fontsize=11, fontweight="bold", color="#0f172a", pad=16)
            axes.set_xlabel("Lần chạy", fontsize=9, color="#64748b")
            axes.set_ylabel(unit, fontsize=9, color="#64748b")
            axes.grid(True, axis="y", color="#e2e8f0", linewidth=0.7)
            axes.set_axisbelow(True)
            axes.spines[["top", "right"]].set_visible(False)
            for side in ("left", "bottom"):
                axes.spines[side].set_color("#e2e8f0")
            axes.tick_params(colors="#64748b", labelsize=8, length=0, pad=8)
            axes.xaxis.set_major_locator(MaxNLocator(integer=True))
            axes.ticklabel_format(axis="y", style="plain", useOffset=False)
            for mechanism, name in NAMES.items():
                items = [r for r in self.results if r.mechanism == mechanism]
                if items:
                    axes.plot([r.run for r in items], [getattr(r, field) for r in items],
                              marker="o", markersize=6, linewidth=2.2,
                              color=COLORS[mechanism], label=name)
            axes.set_ylim(bottom=0)
            if not self.results:
                axes.set_xticks([])
                axes.set_yticks([])
                axes.text(0.5, 0.5, "Kết quả sẽ xuất hiện tại đây", transform=axes.transAxes,
                          ha="center", va="center", fontsize=9, color="#94a3b8")
        self.canvas.draw_idle()

    @pyqtSlot(str)
    def _finished(self, message):
        self.worker = None
        self._set_running(False)
        self.badge.setText("HOÀN TẤT" if message == "Benchmark hoàn tất." else "ĐÃ DỪNG" if message.startswith("Đã dừng") else "CÓ LỖI")
        self.status_label.setText(message)
