import os
from pathlib import Path
from PySide6.QtGui import QFontDatabase
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
from pointer.paths import ROOT

CHECK_ICON_PATH = (ROOT / 'assets' / 'check.png').resolve().as_posix()

STYLE = '''
/* ==========================================================================
   POINTER · Modern Fluent Obsidian & Aurora Studio Design System
   ========================================================================== */

/* Global resets & typography */
QWidget {
    font-family: "Segoe UI Variable Text", "Segoe UI", "PingFang SC", "Microsoft YaHei UI", -apple-system, sans-serif;
    font-size: 13px;
    color: #f1f5f9;
    outline: none;
}

QMainWindow {
    background-color: #0b0f19;
}

#rootWidget {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #080c16, stop:0.5 #0d121f, stop:1 #0b0f19);
}

#content {
    background: transparent;
}

/* ==========================================================================
   Top Header Bar & Floating Capsule Navigation
   ========================================================================== */
#topHeader {
    background: rgba(13, 18, 31, 0.92);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

#brandTitle {
    font-size: 18px;
    font-weight: 800;
    color: #ffffff;
    letter-spacing: 0.5px;
}

#brandBadge {
    font-size: 10px;
    font-weight: 700;
    color: #2cb6ad;
    background: rgba(44, 182, 173, 0.15);
    border: 1px solid rgba(44, 182, 173, 0.35);
    border-radius: 6px;
    padding: 2px 7px;
    letter-spacing: 0.8px;
}

#brandSub {
    font-size: 11px;
    color: #64748b;
}

/* Floating Capsule Navigation Pill Container */
#navCapsule {
    background-color: rgba(15, 23, 42, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 20px;
    padding: 3px 4px;
}

#navCapsule QPushButton {
    color: #94a3b8;
    background-color: transparent;
    border: none;
    border-radius: 16px;
    padding: 7px 16px;
    font-size: 12.5px;
    font-weight: 600;
    text-align: center;
}

#navCapsule QPushButton:hover {
    color: #f8fafc;
    background-color: rgba(255, 255, 255, 0.07);
}

#navCapsule QPushButton:checked {
    color: #ffffff;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(20, 184, 166, 0.32), stop:1 rgba(44, 182, 173, 0.22));
    border: 1.5px solid #2cb6ad;
    font-weight: 700;
}

#headerStatusChip {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 5px 12px;
}

#headerVersion {
    font-size: 11px;
    color: #64748b;
    font-weight: 500;
}

/* ==========================================================================
   Page Titles & Breadcrumb Banner
   ========================================================================== */
#bannerBar {
    background: rgba(17, 24, 39, 0.45);
    border: 1px solid rgba(255, 255, 255, 0.05);
    border-radius: 12px;
    padding: 10px 16px;
}

#pageTitle {
    font-size: 20px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.3px;
}

#subtitle {
    font-size: 12.5px;
    color: #94a3b8;
    line-height: 1.4;
}

#muted {
    font-size: 11.5px;
    color: #64748b;
}

/* ==========================================================================
   Cards & Surfaces (Mica / Frosted Glass)
   ========================================================================== */
#card {
    background-color: rgba(17, 24, 39, 0.85);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 14px;
}

#card:hover {
    border-color: rgba(44, 182, 173, 0.25);
}

#sectionTitle {
    font-size: 14.5px;
    font-weight: 700;
    color: #f8fafc;
    letter-spacing: -0.2px;
}

#previewTitle {
    font-size: 15px;
    font-weight: 700;
    color: #f8fafc;
}

/* ==========================================================================
   Buttons & Interactive Elements
   ========================================================================== */
QPushButton {
    background-color: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 9px;
    padding: 8px 16px;
    font-weight: 500;
    font-size: 12.5px;
    color: #f1f5f9;
}

QPushButton:hover {
    border-color: #2cb6ad;
    background-color: rgba(44, 182, 173, 0.12);
    color: #5eead4;
}

QPushButton:pressed {
    background-color: rgba(44, 182, 173, 0.22);
    border-color: #14b8a6;
    color: #ffffff;
}

QPushButton:focus, QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {
    border: 1.5px solid #2cb6ad;
}

QPushButton:disabled {
    color: #475569;
    background-color: rgba(255, 255, 255, 0.02);
    border-color: rgba(255, 255, 255, 0.04);
}

/* Primary Action Button (Radiant Emerald-Aurora Gradient) */
#applyButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0d9488, stop:1 #2cb6ad);
    color: #ffffff;
    border: none;
    font-weight: 700;
    font-size: 13px;
    padding: 9px 24px;
    border-radius: 10px;
}

#applyButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0f766e, stop:1 #249992);
}

#applyButton:pressed {
    background-color: #115e59;
}

#applyButton:disabled {
    background-color: rgba(255, 255, 255, 0.06);
    color: #475569;
}

/* Tactile Motion Preview Trigger Button */
#motionPreviewButton {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(44, 182, 173, 0.18), stop:1 rgba(56, 189, 248, 0.15));
    border: 1.5px solid rgba(44, 182, 173, 0.5);
    border-radius: 10px;
    color: #5eead4;
    font-weight: 600;
    font-size: 13px;
    padding: 10px;
}

#motionPreviewButton:hover {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(44, 182, 173, 0.28), stop:1 rgba(56, 189, 248, 0.22));
    border-color: #2cb6ad;
    color: #ffffff;
}

#motionPreviewButton:pressed {
    background: rgba(44, 182, 173, 0.4);
    border-color: #5eead4;
    color: #ffffff;
}

/* Inputs & Combos */
QComboBox, QLineEdit, QPlainTextEdit {
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 9px;
    padding: 8px 12px;
    background-color: #131c2e;
    color: #f8fafc;
}

QComboBox:hover {
    border-color: rgba(44, 182, 173, 0.5);
}

QComboBox::drop-down {
    border: none;
    width: 28px;
}

QComboBox QAbstractItemView {
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 9px;
    background-color: #0f172a;
    selection-background-color: rgba(44, 182, 173, 0.25);
    selection-color: #5eead4;
    color: #f8fafc;
    padding: 4px;
}

/* Sliders */
QSlider::groove:horizontal {
    height: 6px;
    background-color: #1e293b;
    border-radius: 3px;
}

QSlider::sub-page:horizontal {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0d9488, stop:1 #2cb6ad);
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background-color: #ffffff;
    border: 2.5px solid #0d9488;
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
}

QSlider::handle:horizontal:hover {
    border-color: #2cb6ad;
    background-color: #ccfbf1;
}

/* Checkbox */
QCheckBox {
    spacing: 10px;
    color: #e2e8f0;
    font-size: 13px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1.5px solid #475569;
    border-radius: 5px;
    background-color: #131c2e;
}

QCheckBox::indicator:hover {
    border-color: #2cb6ad;
}

QCheckBox::indicator:checked {
    background-color: #0d9488;
    border-color: #14b8a6;
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
    background-color: rgba(255, 255, 255, 0.15);
    border-radius: 3px;
    min-height: 36px;
}

QScrollBar::handle:vertical:hover {
    background-color: rgba(44, 182, 173, 0.5);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

/* ==========================================================================
   Floating Bottom Island & Feedback Capsule
   ========================================================================== */
#controlBar {
    background-color: rgba(15, 23, 42, 0.92);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 14px;
    padding: 8px 16px;
}

#feedback {
    background-color: rgba(44, 182, 173, 0.1);
    color: #5eead4;
    border: 1px solid rgba(44, 182, 173, 0.22);
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 500;
}

/* Preset Cards */
.presetCard {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 10px;
}

.presetCard:hover {
    border-color: #2cb6ad;
    background-color: rgba(44, 182, 173, 0.1);
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
    layout.setContentsMargins(20, 18, 20, 20)
    layout.setSpacing(12)
    label = QLabel(title)
    label.setObjectName('sectionTitle')
    layout.addWidget(label)
    if description:
        desc_label = QLabel(description)
        desc_label.setObjectName('muted')
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
    return frame, layout
