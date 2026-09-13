"""Dark theme stylesheet for Kalium."""

STYLESHEET = """
QWidget {
    background-color: #1a1a1f;
    color: #ffffff;
    font-size: 14px;
}
QMainWindow, QDialog {
    background-color: #1a1a1f;
}
QFrame#sidebar {
    background-color: #23232b;
    border-right: 1px solid #35354a;
}
QPushButton {
    background-color: #2d2d38;
    color: #ffffff;
    border: none;
    border-radius: 4px;
    padding: 8px 16px;
    min-height: 28px;
}
QPushButton:hover {
    background-color: #35354a;
}
QPushButton:pressed {
    background-color: #2d2d38;
}
QPushButton:disabled {
    color: #666666;
    background-color: #23232b;
}
QPushButton#primary {
    background-color: #6496ff;
}
QPushButton#primary:hover {
    background-color: #7496ff;
}
QPushButton#danger {
    background-color: #804040;
}
QPushButton#danger:hover {
    background-color: #904040;
}
QPushButton#nav {
    text-align: left;
    padding-left: 12px;
    background-color: transparent;
}
QPushButton#nav:checked {
    background-color: #35354a;
}
QLineEdit, QComboBox, QSpinBox {
    background-color: #1a1a1f;
    border: 1px solid #35354a;
    border-radius: 4px;
    padding: 6px 8px;
    min-height: 24px;
}
QLineEdit:focus, QComboBox:focus {
    border-color: #6496ff;
}
QProgressBar {
    background-color: #1a1a1f;
    border-radius: 4px;
    text-align: center;
    min-height: 10px;
    max-height: 14px;
}
QProgressBar::chunk {
    background-color: #6496ff;
    border-radius: 4px;
}
QLabel#title {
    font-size: 24px;
    font-weight: 700;
}
QLabel#section {
    font-size: 18px;
    font-weight: 600;
}
QLabel#muted {
    color: #a0a0a0;
}
QLabel#success {
    color: #64c864;
}
QLabel#error {
    color: #ff6464;
}
QScrollArea {
    border: none;
}
QListWidget {
    background-color: #23232b;
    border: 1px solid #35354a;
    border-radius: 6px;
}
QListWidget::item {
    padding: 10px;
}
QListWidget::item:selected {
    background-color: #283c28;
}
QTextEdit, QPlainTextEdit {
    background-color: #23232b;
    border: 1px solid #35354a;
    border-radius: 4px;
}
QCheckBox, QRadioButton {
    spacing: 8px;
}
QGroupBox {
    border: 1px solid #35354a;
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 12px;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
}
"""
