import os
from pathlib import Path
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from pointer.paths import ROOT

CHECK_ICON_PATH = (ROOT / 'assets' / 'check.png').resolve().as_posix()

STYLE = '''
/* Global resets & typography */
QWidget {
    font-family: "Segoe UI Variable Text", "Segoe UI", "Microsoft YaHei UI", -apple-system, sans-serif;
    font-size: 13px;
    color: #1e293b;
    outline: none;
}

QMainWindow, #content {
    background-color: #f1f5f9;
}

/* Sidebar - Frosted Dark Slate Acrylic */
#sidebar {
    background-color: #111827;
    border-right: 1px solid rgba(255, 255, 255, 0.07);
}

#sidebar QLabel {
    color: #94a3b8;
    background: transparent;
}

#brand {
    font-size: 24px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.5px;
}

#sidebarSub {
    font-size: 11px;
    color: #64748b;
    margin-top: 2px;
}

#sidebar QPushButton {
    color: #94a3b8;
    background-color: transparent;
    border: none;
    border-left: 3px solid transparent;
    text-align: left;
    padding: 12px 16px;
    border-radius: 9px;
    font-size: 13px;
    font-weight: 500;
    margin-bottom: 4px;
}

#sidebar QPushButton:hover {
    background-color: rgba(255, 255, 255, 0.06);
    color: #f8fafc;
}

#sidebar QPushButton:checked {
    background-color: rgba(44, 182, 173, 0.16);
    color: #ffffff;
    font-weight: 600;
    border-left: 3px solid #2cb6ad;
}

#sidebarStatusCard {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 10px 12px;
}

#sidebarStatusText {
    font-size: 11px;
    color: #38bdf8;
    font-weight: 600;
}

#sidebarVersion {
    font-size: 11px;
    color: #475569;
}

/* Page Header */
#pageTitle {
    font-size: 26px;
    font-weight: 700;
    color: #0f172a;
    letter-spacing: -0.5px;
}

#subtitle {
    font-size: 13px;
    color: #64748b;
    line-height: 1.4;
}

#muted {
    font-size: 12px;
    color: #64748b;
}

/* Cards - Apple/macOS Frosted Glass Card */
#card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 14px;
}

#sectionTitle {
    font-size: 15px;
    font-weight: 600;
    color: #0f172a;
}

#previewTitle {
    font-size: 17px;
    font-weight: 600;
    color: #0f172a;
}

/* Buttons */
QPushButton {
    background-color: #ffffff;
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
    color: #1e293b;
}

QPushButton:hover {
    border-color: #2cb6ad;
    background-color: #f0fdfa;
    color: #115e59;
}

QPushButton:pressed {
    background-color: #e6f7f6;
    border-color: #207a75;
}

QPushButton:focus, QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {
    border: 1.5px solid #2cb6ad;
}

QPushButton:disabled {
    color: #94a3b8;
    background-color: #f1f5f9;
    border-color: #e2e8f0;
}

/* Primary Action Button (Emerald to Aurora Gradient) */
#applyButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a6d68, stop:1 #28a9a1);
    color: #ffffff;
    border: none;
    font-weight: 600;
    font-size: 13px;
    padding: 10px 24px;
    border-radius: 8px;
}

#applyButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #155b57, stop:1 #22938c);
}

#applyButton:pressed {
    background-color: #134e4a;
}

#applyButton:disabled {
    background-color: #99c2bf;
    color: rgba(255, 255, 255, 0.7);
}

/* Inputs & Combos */
QComboBox, QLineEdit, QPlainTextEdit {
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    padding: 8px 12px;
    background-color: #ffffff;
    color: #0f172a;
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox QAbstractItemView {
    border: 1px solid #cbd5e1;
    border-radius: 8px;
    background-color: #ffffff;
    selection-background-color: #f0fdfa;
    selection-color: #115e59;
    padding: 4px;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background-color: #e2e8f0;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1a6d68, stop:1 #2cb6ad);
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background-color: #ffffff;
    border: 2px solid #207a75;
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
}

QSlider::handle:horizontal:hover {
    border-color: #2cb6ad;
    background-color: #f0fdfa;
}

/* Checkbox */
QCheckBox {
    spacing: 10px;
    color: #1e293b;
    font-size: 13px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1.5px solid #cbd5e1;
    border-radius: 5px;
    background-color: #ffffff;
}

QCheckBox::indicator:hover {
    border-color: #2cb6ad;
}

QCheckBox::indicator:checked {
    background-color: #207a75;
    border-color: #207a75;
    image: url("__CHECK_ICON__");
}

/* ScrollArea & ScrollBar */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    width: 6px;
    background: transparent;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: #cbd5e1;
    border-radius: 3px;
    min-height: 36px;
}

QScrollBar::handle:vertical:hover {
    background-color: #94a3b8;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* Bottom Bar & Feedback */
#controlBar {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 12px;
    padding: 10px 16px;
}

#feedback {
    background-color: #e6f7f6;
    color: #115e59;
    border-radius: 8px;
    padding: 10px 14px;
    font-size: 12px;
    font-weight: 500;
}

/* Preset Cards */
.presetCard {
    background-color: #f8fafc;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    padding: 10px;
}

.presetCard:hover {
    border-color: #2cb6ad;
    background-color: #f0fdfa;
}
'''.replace('__CHECK_ICON__', CHECK_ICON_PATH)


def initialize_fonts():
    # The offscreen Qt platform has no system font database on Windows.
    # Read the user's installed fonts for checks; never redistribute them.
    if not QFontDatabase.families():
        fonts = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'Fonts'
        for filename in ('msyh.ttc', 'msyhbd.ttc'):
            path = fonts / filename
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))


def card(title, description=None):
    frame = QFrame()
    frame.setObjectName('card')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(22, 20, 22, 22)
    layout.setSpacing(14)
    label = QLabel(title)
    label.setObjectName('sectionTitle')
    layout.addWidget(label)
    if description:
        desc_label = QLabel(description)
        desc_label.setObjectName('muted')
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
    return frame, layout
