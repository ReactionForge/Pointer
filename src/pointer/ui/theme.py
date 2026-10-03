import os
from pathlib import Path
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout

STYLE = '''
QWidget { font-family: "Microsoft YaHei UI"; font-size: 13px; color: #202a35; }
QMainWindow, #content { background: #f3f5f7; }
#sidebar { background: #202830; }
#sidebar QLabel { color: #d6dce2; background: transparent; }
#brand { font-size: 27px; font-weight: 700; color: white; }
#sidebar QPushButton { color: #b8c2cc; background: transparent; border: none; text-align: left; padding: 14px 17px; border-radius: 8px; }
#sidebar QPushButton:checked { background: #394854; color: white; font-weight: 600; }
#sidebar QPushButton:hover { background: #303d48; }
#pageTitle { font-size: 26px; font-weight: 700; }
#subtitle, #muted { color: #71808e; }
#card { background: white; border: 1px solid #e0e6eb; border-radius: 12px; }
#sectionTitle { font-size: 16px; font-weight: 600; }
#previewTitle { font-size: 19px; font-weight: 600; }
QPushButton { background: white; border: 1px solid #d6dfe6; border-radius: 7px; padding: 9px 14px; }
QPushButton:hover { border-color: #2b7a79; background: #eff8f7; }
QPushButton:focus, QComboBox:focus, QLineEdit:focus { border: 2px solid #368784; }
QPushButton:disabled { color: #98a4af; background: #edf0f3; }
#applyButton { background: #216e6c; color: white; border: none; font-weight: 600; padding: 11px 24px; }
#applyButton:hover { background: #175956; }
#applyButton:disabled { background: #97b7b5; }
QComboBox, QLineEdit, QPlainTextEdit { border: 1px solid #d6dfe6; border-radius: 6px; padding: 8px; background: white; }
QComboBox::drop-down { border: none; width: 25px; }
QSlider::groove:horizontal { height: 5px; background: #dfe6eb; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #398884; border-radius: 2px; }
QSlider::handle:horizontal { background: #216e6c; width: 16px; margin: -6px 0; border-radius: 8px; }
QCheckBox { spacing: 9px; }
QCheckBox::indicator { width: 18px; height: 18px; }
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { width: 8px; background: transparent; }
QScrollBar::handle:vertical { background: #c6d0d8; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
#feedback { background: #e5efee; color: #285d59; border-radius: 6px; padding: 9px; }
'''


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
    layout.setContentsMargins(20, 18, 20, 20)
    layout.setSpacing(13)
    label = QLabel(title)
    label.setObjectName('sectionTitle')
    layout.addWidget(label)
    if description:
        label = QLabel(description)
        label.setObjectName('muted')
        label.setWordWrap(True)
        layout.addWidget(label)
    return frame, layout
