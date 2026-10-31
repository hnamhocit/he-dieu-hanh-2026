"""Bảng màu và kiểu hiển thị theo wireframe desktop IPC."""

STYLESHEET = """
QMainWindow, QScrollArea, QWidget#page { background: #f5f8fc; }
QWidget { font-family: 'Segoe UI'; font-size: 12px; color: #243b53; }
QFrame#titleBar { background: #284f7d; border-radius: 7px; }
QLabel#appTitle { color: white; font-size: 18px; font-weight: 600; }
QLabel#modeBadge { color: #dbeafe; font-size: 11px; }
QGroupBox {
    background: white; border: 1px dashed #9bbbd4; border-radius: 7px;
    margin-top: 9px; padding: 10px 10px 8px; font-weight: 600;
}
QGroupBox::title { subcontrol-origin: margin; left: 14px; padding: 0 5px; }
QGroupBox#configGroup { border-color: #b6a2c9; }
QGroupBox#bufferGroup { border-color: #70b7a3; }
QGroupBox#traceGroup { border-color: #dfbb65; }
QFrame#fileInfo { background: #eef5fd; border: 1px solid #dce7f4; border-radius: 5px; }
QFrame#producerCard { background: #eff7ff; border: 1px solid #c5dbea; border-radius: 5px; }
QFrame#bufferCard { background: #fffbed; border: 1px solid #eadfa8; border-radius: 5px; }
QFrame#consumerCard { background: #effbf5; border: 1px solid #bfe4d6; border-radius: 5px; }
QFrame#chartCard, QFrame#statsCard {
    background: white; border: 1px solid #dce5ed; border-radius: 5px;
}
QLabel#cardTitle { font-weight: 600; font-size: 13px; }
QLabel#readyBadge { background: #d8f5e8; color: #14745b; border-radius: 9px; padding: 3px 10px; }
QLabel#arrow { color: #3c83b5; font-size: 29px; }
QLabel#flow { background: #f0eef9; color: #5f548a; border-radius: 5px; padding: 9px; }
QLineEdit, QSpinBox, QComboBox {
    background: white; color: #243b53; border: 1px solid #cdd9e5;
    border-radius: 4px; padding: 5px; min-height: 16px;
}
QPushButton {
    background: #f0f7fe; color: #285f8d; border: 1px solid #adc9df;
    border-radius: 4px; padding: 7px 12px; min-height: 16px;
}
QPushButton:hover { background: #e1effc; }
QPushButton#startButton { background: #21a369; color: white; border-color: #21a369; font-weight: 600; }
QPushButton#pauseButton { background: #ffda79; color: #624c17; border-color: #efcc70; font-weight: 600; }
QPushButton#resetButton { background: #ffc4c4; color: #9a3131; border-color: #edaaaa; font-weight: 600; }
QPushButton:disabled, QPushButton#startButton:disabled,
QPushButton#pauseButton:disabled, QPushButton#resetButton:disabled {
    background: #edf1f5; color: #94a3b4; border-color: #dbe2eb;
}
QProgressBar { border: none; background: #e6edf1; border-radius: 4px; max-height: 9px; }
QProgressBar::chunk { background: #40a5d4; border-radius: 4px; }
QTableWidget { background: white; alternate-background-color: #f6f9fc;
    gridline-color: #e5ecf3; border: 1px solid #dce5ed; selection-background-color: #dceeff; }
QHeaderView::section { background: #eef3f9; padding: 6px; border: 1px solid #e0e8f0; }
QStatusBar { color: #5a7085; }
"""
