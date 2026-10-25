"""Bảng màu và kiểu hiển thị hiện đại, phân tách rõ ràng cho desktop IPC Simulator."""

STYLESHEET = """
QMainWindow, QScrollArea, QWidget#page {
    background: #edf2f7;
}

QWidget {
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', sans-serif;
    font-size: 12px;
    color: #1e293b;
}

/* Thanh tiêu đề Header */
QFrame#titleBar {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f172a, stop:0.5 #1e3a8a, stop:1 #2563eb);
    border-radius: 8px;
    padding: 2px 8px;
}

QLabel#appTitle {
    color: #ffffff;
    font-size: 16px;
    font-weight: 700;
    letter-spacing: 0.5px;
}

QLabel#modeBadge {
    background: rgba(255, 255, 255, 0.2);
    color: #ffffff;
    font-size: 11px;
    font-weight: 700;
    border-radius: 4px;
    padding: 4px 10px;
    border: 1px solid rgba(255, 255, 255, 0.3);
}

/* Các phân khu GroupBox */
QGroupBox {
    background: #ffffff;
    border: 1.5px solid #cbd5e1;
    border-radius: 8px;
    margin-top: 8px;
    padding: 8px 10px 6px;
    font-weight: 700;
    font-size: 13px;
    color: #0f172a;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 6px;
    background: #ffffff;
    border-radius: 4px;
}

QGroupBox#configGroup {
    border-color: #cbd5e1;
}

QGroupBox#bufferGroup {
    border-color: #cbd5e1;
}

QGroupBox#traceGroup {
    border-color: #cbd5e1;
}

/* Thẻ thông tin file CSV */
QFrame#fileInfo {
    background: #f8fafc;
    border: 1.5px solid #e2e8f0;
    border-radius: 6px;
    padding: 4px;
}

/* Thẻ Producer (Xanh dương / Indigo nổi bật) */
QFrame#producerCard {
    background: #f0f7ff;
    border: 1.5px solid #93c5fd;
    border-top: 4px solid #2563eb;
    border-radius: 8px;
}

/* Thẻ Shared Buffer (Vàng hổ phách nổi bật) */
QFrame#bufferCard {
    background: #fffdf5;
    border: 1.5px solid #fde047;
    border-top: 4px solid #f59e0b;
    border-radius: 8px;
}

/* Thẻ Consumer (Xanh lục ngọc nổi bật) */
QFrame#consumerCard {
    background: #f0fdf4;
    border: 1.5px solid #86efac;
    border-top: 4px solid #16a34a;
    border-radius: 8px;
}

/* Thẻ Biểu đồ và Thống kê */
QFrame#chartCard {
    background: #ffffff;
    border: 1.5px solid #e2e8f0;
    border-radius: 8px;
}

QFrame#statsCard {
    background: #f8fafc;
    border: 1.5px solid #e2e8f0;
    border-radius: 8px;
}

QLabel#cardTitle {
    font-weight: 700;
    font-size: 13px;
    color: #0f172a;
}

QLabel#readyBadge {
    background: #dcfce7;
    color: #15803d;
    font-weight: 700;
    font-size: 11px;
    border: 1px solid #86efac;
    border-radius: 10px;
    padding: 2px 10px;
}

QLabel#arrow {
    color: #2563eb;
    font-size: 26px;
    font-weight: 900;
}

/* Thống kê nhanh */
QLabel#statTotal { font-weight: 700; color: #0f172a; font-size: 13px; }
QLabel#statProcessed { font-weight: 700; color: #16a34a; font-size: 13px; }
QLabel#statFailed { font-weight: 700; color: #ef4444; font-size: 13px; }
QLabel#statThroughput { font-weight: 700; color: #2563eb; font-size: 13px; }

/* Điều khiển Input, SpinBox, ComboBox */
QLineEdit, QSpinBox, QComboBox {
    background: #ffffff;
    color: #0f172a;
    border: 1.5px solid #cbd5e1;
    border-radius: 6px;
    padding: 5px 8px;
    min-height: 18px;
    font-size: 12px;
}

QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border-color: #2563eb;
}

QSpinBox:disabled, QComboBox:disabled {
    background: #f1f5f9;
    color: #94a3b8;
    border-color: #e2e8f0;
}

/* Các nút bấm (Buttons) nổi bật rõ ràng */
QPushButton {
    background: #ffffff;
    color: #1e293b;
    border: 1.5px solid #cbd5e1;
    border-radius: 6px;
    padding: 6px 12px;
    min-height: 16px;
    font-weight: 600;
}

QPushButton:hover {
    background: #f1f5f9;
    border-color: #94a3b8;
}

QPushButton#browseButton {
    background: #f8fafc;
    color: #1e293b;
    border: 1.5px solid #cbd5e1;
}

QPushButton#browseButton:hover {
    background: #e2e8f0;
    border-color: #94a3b8;
}

QPushButton#checkButton {
    background: #2563eb;
    color: #ffffff;
    border: 1.5px solid #1d4ed8;
    font-weight: 700;
}

QPushButton#checkButton:hover {
    background: #1d4ed8;
}

QPushButton#startButton {
    background: #16a34a;
    color: #ffffff;
    border: 1.5px solid #15803d;
    font-weight: 700;
    font-size: 13px;
}

QPushButton#startButton:hover {
    background: #15803d;
}

QPushButton#pauseButton {
    background: #f59e0b;
    color: #ffffff;
    border: 1.5px solid #d97706;
    font-weight: 700;
    font-size: 13px;
}

QPushButton#pauseButton:hover {
    background: #d97706;
}

QPushButton#resetButton {
    background: #ef4444;
    color: #ffffff;
    border: 1.5px solid #dc2626;
    font-weight: 700;
    font-size: 13px;
}

QPushButton#resetButton:hover {
    background: #dc2626;
}

QPushButton:disabled, QPushButton#startButton:disabled,
QPushButton#pauseButton:disabled, QPushButton#resetButton:disabled,
QPushButton#checkButton:disabled, QPushButton#exportButton:disabled {
    background: #f1f5f9;
    color: #94a3b8;
    border-color: #e2e8f0;
}

QPushButton#exportButton {
    background: #0284c7;
    color: #ffffff;
    border: 1.5px solid #0369a1;
    font-weight: 700;
    padding: 7px 16px;
}

QPushButton#exportButton:hover {
    background: #0369a1;
}

/* Thanh tiến độ Buffer */
QProgressBar {
    border: 1px solid #e2e8f0;
    background: #f1f5f9;
    border-radius: 4px;
    max-height: 10px;
}

QProgressBar::chunk {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #3b82f6, stop:1 #2563eb);
    border-radius: 4px;
}

/* Bảng Trace Log */
QTableWidget {
    background: #ffffff;
    alternate-background-color: #f8fafc;
    gridline-color: #e2e8f0;
    border: 1.5px solid #cbd5e1;
    border-radius: 6px;
    selection-background-color: #dbeafe;
    selection-color: #1e3a8a;
}

QHeaderView::section {
    background: #f1f5f9;
    color: #0f172a;
    font-weight: 700;
    padding: 7px;
    border: 1px solid #cbd5e1;
    border-top: none;
}

QStatusBar {
    color: #64748b;
    font-size: 11px;
    background: #f8fafc;
    border-top: 1px solid #e2e8f0;
}
"""
