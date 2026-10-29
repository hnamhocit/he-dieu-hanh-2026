"""Các vùng vẽ của layout; khởi tạo rỗng, không sinh dữ liệu mô phỏng giả."""

from copy import deepcopy
from html import escape

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class BufferSlots(QWidget):
    COLORS = {
        "EMPTY": "#f8fafc",
        "LOCKED": "#fef3c7",
        "WRITING": "#ede9fe",
        "WRITTEN": "#dcfce7",
        "READING": "#dbeafe",
    }
    BORDER_COLORS = {
        "EMPTY": "#cbd5e1",
        "LOCKED": "#f59e0b",
        "WRITING": "#8b5cf6",
        "WRITTEN": "#10b981",
        "READING": "#2563eb",
    }
    TEXT_COLORS = {
        "EMPTY": "#64748b",
        "LOCKED": "#b45309",
        "WRITING": "#6d28d9",
        "WRITTEN": "#047857",
        "READING": "#1d4ed8",
    }
    LABELS = {
        "EMPTY": "Trống",
        "LOCKED": "Đang khóa",
        "WRITING": "Đang ghi",
        "WRITTEN": "Đã ghi",
        "READING": "Đang đọc",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.capacity = 5
        self.buffer = [None] * self.capacity
        self.active_slot = None
        self.phase = None
        self.first_visible = 0
        self._hit_boxes = []
        self.setMinimumHeight(108)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Các ô nhớ của buffer")

    def set_capacity(self, capacity: int) -> None:
        if capacity <= 0:
            raise ValueError("Dung lượng buffer phải lớn hơn 0.")
        self.capacity = capacity
        self.buffer = [None] * capacity
        self.active_slot = None
        self.phase = None
        self.first_visible = 0
        self._hit_boxes = []
        self.setToolTip("")
        self.update()

    def set_snapshot(self, snapshot: dict) -> None:
        self.capacity = snapshot["capacity"]
        self.buffer = deepcopy(snapshot["buffer"])
        self.active_slot = None
        self.phase = None
        self.first_visible = min(self.first_visible, self.capacity - 1)
        # Không dùng vùng hover cũ trong khi chờ Qt vẽ snapshot mới.
        self._hit_boxes = []
        self.setToolTip("")
        self.update()

    def set_frame(self, frame: dict) -> None:
        self.set_snapshot(frame["snapshot"])
        self.active_slot = frame["slot_index"]
        self.phase = frame["phase"]
        visible = self.visible_count()
        if not self.first_visible <= self.active_slot < self.first_visible + visible:
            self.first_visible = min(self.active_slot, max(0, self.capacity - visible))
        self.update()

    def visible_count(self):
        return min(self.capacity, max(1, self.width() // 92))

    def slot_state(self, index):
        if index == self.active_slot and self.phase in ("LOCKED", "WRITING", "READING"):
            return self.phase
        return "EMPTY" if self.buffer[index] is None else "WRITTEN"

    def wheelEvent(self, event):
        direction = -1 if event.angleDelta().y() > 0 else 1
        self._move_page(direction)
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            self._move_page(-1 if event.key() == Qt.Key.Key_Left else 1)
        else:
            super().keyPressEvent(event)

    def _move_page(self, direction):
        visible = self.visible_count()
        self.first_visible = max(0, min(
            self.first_visible + direction * visible, self.capacity - visible,
        ))
        self.update()

    def mouseMoveEvent(self, event):
        for rect, index in self._hit_boxes:
            if rect.contains(event.position()):
                item = self.buffer[index]
                detail = (f"M{item.get('id', '?')}: {item.get('message', '')}"
                          if isinstance(item, dict) else str(item) if item is not None else "")
                self.setToolTip("<pre>" + escape(
                    f"Ô {index}: {self.LABELS[self.slot_state(index)]}\n{detail}"
                ) + "</pre>")
                return
        self.setToolTip("")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        visible = self.visible_count()
        self.first_visible = min(self.first_visible, self.capacity - visible)
        slot_width = min(140, max(1, self.width()) / visible)
        start_x = (self.width() - visible * slot_width) / 2
        self._hit_boxes = []

        for offset in range(visible):
            index = self.first_visible + offset
            item = self.buffer[index]
            state = self.slot_state(index)
            text = (f"M{item.get('id', '?')}" if isinstance(item, dict)
                    else str(item) if item is not None else "")
            rect = QRectF(
                start_x + offset * slot_width,
                24,
                max(1, slot_width - 6),
                56,
            )
            self._hit_boxes.append((rect, index))

            # Vẽ nền và viền ô rõ nét, nổi bật theo trạng thái
            border_color = self.BORDER_COLORS.get(state, "#94a3b8")
            pen_width = 2.0 if state in ("LOCKED", "WRITING", "READING") else 1.5
            painter.setPen(QPen(QColor(border_color), pen_width))
            painter.setBrush(QColor(self.COLORS[state]))
            painter.drawRoundedRect(rect, 6, 6)

            # Vẽ tên ô ở phía trên
            painter.setPen(QColor("#334155"))
            painter.drawText(
                QRectF(rect.x(), 2, rect.width(), 20),
                Qt.AlignmentFlag.AlignCenter,
                f"Ô {index}",
            )

            # Nhãn trạng thái nổi bật
            painter.setPen(QColor(self.TEXT_COLORS.get(state, "#475569")))
            font = painter.font()
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                QRectF(rect.x(), rect.y() + 4, rect.width(), 24),
                Qt.AlignmentFlag.AlignCenter,
                self.LABELS[state],
            )
            font.setBold(False)
            painter.setFont(font)

            label = painter.fontMetrics().elidedText(
                text,
                Qt.TextElideMode.ElideRight,
                max(1, int(rect.width() - 8)),
            )

            # Dữ liệu bên trong ô
            painter.setPen(QColor("#0f172a"))
            painter.drawText(
                QRectF(rect.x(), rect.y() + 28, rect.width(), 24),
                Qt.AlignmentFlag.AlignCenter,
                label,
            )

        painter.setPen(QColor("#64748b"))
        hint = f"Ô {self.first_visible}–{self.first_visible + visible - 1} / {self.capacity}"
        if visible < self.capacity:
            hint += " · Cuộn / phím ← → để xem thêm"
        painter.drawText(QRectF(0, 84, self.width(), 22), Qt.AlignmentFlag.AlignCenter, hint)


class BufferChart(QWidget):
    """Mức sử dụng buffer thực tế sau mỗi bước CSV, tối đa 500 mẫu gần nhất."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.samples = []
        self.setMinimumHeight(90)
        self.setAccessibleName("Biểu đồ mức sử dụng buffer theo thời gian")

    def reset(self):
        self.samples.clear()
        self.update()

    def add_sample(self, elapsed, count, capacity):
        self.samples.append((elapsed, count * 100 / capacity))
        self.samples = self.samples[-500:]
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = QRectF(40, 12, max(1, self.width() - 58), max(1, self.height() - 36))
        for value in (0, 50, 100):
            y = plot.bottom() - plot.height() * value / 100
            painter.setPen(QPen(QColor("#e2e8f0"), 1))
            painter.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
            painter.setPen(QColor("#64748b"))
            painter.drawText(QRectF(0, y - 9, 34, 18), Qt.AlignmentFlag.AlignRight,
                             f"{value}%")
        painter.setPen(QPen(QColor("#cbd5e1"), 1.5))
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())
        painter.drawLine(plot.bottomLeft(), plot.topLeft())
        painter.setPen(QColor("#64748b"))
        if not self.samples:
            painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "Chưa có dữ liệu mô phỏng")
        else:
            first = self.samples[0][0]
            span = max(0.001, self.samples[-1][0] - first)
            points = [(plot.left() + (time - first) / span * plot.width(),
                       plot.bottom() - value / 100 * plot.height())
                      for time, value in self.samples]
            painter.setPen(QPen(QColor("#2563eb"), 2.5))
            for (x1, y1), (x2, y2) in zip(points, points[1:]):
                painter.drawLine(int(x1), int(y1), int(x2), int(y2))
            painter.setBrush(QColor("#2563eb"))
            for x, y in points:
                painter.drawEllipse(QRectF(x - 3, y - 3, 6, 6))
            painter.setPen(QColor("#1e293b"))
            painter.drawText(plot, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
                             f"{first:.1f}–{self.samples[-1][0]:.1f} s")
        painter.setPen(QColor("#64748b"))
        painter.drawText(QRectF(plot.left(), plot.bottom() + 5, plot.width(), 20),
                         Qt.AlignmentFlag.AlignRight, "Thời gian (s)")
