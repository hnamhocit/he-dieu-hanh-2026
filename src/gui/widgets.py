"""Các vùng vẽ của layout; khởi tạo rỗng, không sinh dữ liệu mô phỏng giả."""

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class BufferSlots(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.capacity = 5
        self.setMinimumHeight(48)
        self.setAccessibleName("Các ô nhớ của buffer")

    def set_capacity(self, capacity: int) -> None:
        self.capacity = capacity
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Giới hạn số ô vẽ để layout vẫn đọc được khi capacity lớn.
        visible = min(self.capacity, max(1, (self.width() - 60) // 30))
        width = min(32, (self.width() - 60) / visible)
        start = (self.width() - visible * width) / 2
        painter.setPen(QPen(QColor("#adc7d8"), 1))
        painter.setBrush(QColor("#eef7fd"))
        for index in range(visible):
            painter.drawRoundedRect(QRectF(start + index * width, 10, width - 2, 28), 3, 3)
        if visible < self.capacity:
            painter.setPen(QColor("#52677b"))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"+{self.capacity - visible}")


class BufferChart(QWidget):
    """Khung biểu đồ trống, chờ dữ liệu từ bộ chạy IPC."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(90)
        self.setAccessibleName("Biểu đồ mức sử dụng buffer theo thời gian")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        plot = QRectF(40, 12, max(1, self.width() - 58), max(1, self.height() - 36))
        for value in (0, 50, 100):
            y = plot.bottom() - plot.height() * value / 100
            painter.setPen(QPen(QColor("#e5edf4"), 1))
            painter.drawLine(int(plot.left()), int(y), int(plot.right()), int(y))
            painter.setPen(QColor("#60758a"))
            painter.drawText(QRectF(0, y - 9, 34, 18), Qt.AlignmentFlag.AlignRight,
                             f"{value}%")
        painter.setPen(QPen(QColor("#bed0df"), 1))
        painter.drawLine(plot.bottomLeft(), plot.bottomRight())
        painter.drawLine(plot.bottomLeft(), plot.topLeft())
        painter.setPen(QColor("#60758a"))
        painter.drawText(plot, Qt.AlignmentFlag.AlignCenter, "Chưa có dữ liệu mô phỏng")
        painter.drawText(QRectF(plot.left(), plot.bottom() + 5, plot.width(), 20),
                         Qt.AlignmentFlag.AlignRight, "Thời gian (s)")
