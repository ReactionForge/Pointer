import os
from pathlib import Path
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QFontDatabase, QPainter, QColor, QPen
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout, QHBoxLayout, QWidget, QCheckBox
from pointer.paths import ROOT

CHECK_ICON_PATH = (ROOT / 'assets' / 'check.png').resolve().as_posix()

STYLE = '''
/* ==========================================================================
   POINTER · Apple macOS Sequoia Design System
   ========================================================================== */

/* Global resets & typography */
QWidget {
    font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI Variable Text", "Segoe UI", "PingFang SC", "Microsoft YaHei UI", sans-serif;
    font-size: 13px;
    color: #f5f5f7;
    outline: none;
}

QMainWindow {
    background-color: #1c1c1e;
}

#rootWidget {
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #232326, stop:0.25 #1c1c1e, stop:1 #171719);
}

#content {
    background: transparent;
}

/* ==========================================================================
   Top Header Bar & macOS Segmented Navigation
   ========================================================================== */
#topHeader {
    background-color: rgba(34, 34, 37, 0.96);
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}

#brandTitle {
    font-size: 15px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.2px;
}

#brandBadge {
    font-size: 10px;
    font-weight: 600;
    color: #98989d;
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 5px;
    padding: 1px 6px;
    letter-spacing: 0.5px;
}

#brandSub {
    font-size: 11px;
    color: #86868b;
}

/* macOS Segmented Control Pill Container */
#navCapsule {
    background-color: rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 2px;
}

#navCapsule QPushButton {
    color: #98989d;
    background-color: transparent;
    border: none;
    border-radius: 6px;
    padding: 5px 16px;
    font-size: 12.5px;
    font-weight: 500;
    text-align: center;
}

#navCapsule QPushButton:hover {
    color: #ffffff;
    background-color: rgba(255, 255, 255, 0.06);
}

#navCapsule QPushButton:checked {
    color: #ffffff;
    background-color: #3e3e42;
    border: 1px solid rgba(255, 255, 255, 0.15);
    font-weight: 600;
}

#headerStatusChip {
    background-color: rgba(255, 255, 255, 0.06);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 4px 11px;
}

#headerVersion {
    font-size: 11px;
    color: #86868b;
    font-weight: 500;
}

/* ==========================================================================
   Page Titles & Banner
   ========================================================================== */
#bannerBar {
    background: transparent;
    border: none;
    padding: 2px 0 6px 0;
}

#pageTitle {
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
    letter-spacing: -0.4px;
}

#subtitle {
    font-size: 13px;
    color: #86868b;
    line-height: 1.4;
}

#muted {
    font-size: 12px;
    color: #86868b;
}

/* ==========================================================================
   macOS Inset Grouped Cards
   ========================================================================== */
QFrame#card {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
}

QFrame#card:hover {
    border-color: rgba(255, 255, 255, 0.14);
}

#sectionTitle {
    font-size: 13.5px;
    font-weight: 600;
    color: #f5f5f7;
    letter-spacing: -0.1px;
}

#previewTitle {
    font-size: 14px;
    font-weight: 600;
    color: #f5f5f7;
}

/* ==========================================================================
   Apple Buttons & Controls
   ========================================================================== */
QPushButton {
    background-color: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 7px 16px;
    font-weight: 500;
    font-size: 12.5px;
    color: #f5f5f7;
}

QPushButton:hover {
    border-color: rgba(255, 255, 255, 0.22);
    background-color: rgba(255, 255, 255, 0.13);
    color: #ffffff;
}

QPushButton:pressed {
    background-color: rgba(255, 255, 255, 0.18);
    border-color: rgba(255, 255, 255, 0.25);
}

QPushButton:focus, QComboBox:focus, QLineEdit:focus, QPlainTextEdit:focus {
    border: 1.5px solid #007aff;
}

QPushButton:disabled {
    color: #636366;
    background-color: rgba(255, 255, 255, 0.02);
    border-color: rgba(255, 255, 255, 0.04);
}

/* Primary Action Button (macOS System Blue) */
#applyButton {
    background-color: #007aff;
    color: #ffffff;
    border: none;
    font-weight: 600;
    font-size: 13px;
    padding: 8px 22px;
    border-radius: 8px;
}

#applyButton:hover {
    background-color: #006ee6;
}

#applyButton:pressed {
    background-color: #0060cc;
}

#applyButton:disabled {
    background-color: rgba(255, 255, 255, 0.06);
    color: #636366;
}

/* Motion Preview Trigger Button */
#motionPreviewButton {
    background-color: rgba(0, 122, 255, 0.12);
    border: 1px solid rgba(0, 122, 255, 0.35);
    border-radius: 8px;
    color: #0a84ff;
    font-weight: 600;
    font-size: 12.5px;
    padding: 9px;
}

#motionPreviewButton:hover {
    background-color: rgba(0, 122, 255, 0.22);
    border-color: #007aff;
    color: #ffffff;
}

#motionPreviewButton:pressed {
    background-color: rgba(0, 122, 255, 0.32);
    border-color: #007aff;
    color: #ffffff;
}

/* Inputs & Combos */
QComboBox, QLineEdit, QPlainTextEdit {
    border: 1px solid rgba(255, 255, 255, 0.12);
    border-radius: 8px;
    padding: 6px 12px;
    background-color: rgba(255, 255, 255, 0.06);
    color: #f5f5f7;
}

QComboBox:hover {
    border-color: rgba(255, 255, 255, 0.22);
    background-color: rgba(255, 255, 255, 0.09);
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 8px;
    background-color: #242426;
    selection-background-color: #007aff;
    selection-color: #ffffff;
    color: #f5f5f7;
    padding: 4px;
}

/* macOS Sliders */
QSlider::groove:horizontal {
    height: 4px;
    background-color: rgba(255, 255, 255, 0.14);
    border-radius: 2px;
}

QSlider::sub-page:horizontal {
    background-color: #007aff;
    border-radius: 2px;
}

QSlider::handle:horizontal {
    background-color: #ffffff;
    border: 1px solid rgba(0, 0, 0, 0.2);
    width: 18px;
    height: 18px;
    margin: -7px 0;
    border-radius: 9px;
}

QSlider::handle:horizontal:hover {
    background-color: #f5f5f7;
}

/* Checkbox & Switch */
QCheckBox {
    spacing: 12px;
    color: #f5f5f7;
    font-size: 13px;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border: 1.5px solid rgba(255, 255, 255, 0.22);
    border-radius: 5px;
    background-color: rgba(255, 255, 255, 0.04);
}

QCheckBox::indicator:hover {
    border-color: #007aff;
}

QCheckBox::indicator:checked {
    background-color: #34c759;
    border-color: #34c759;
    image: url("__CHECK_ICON__");
}

/* ScrollArea & ScrollBar */
QScrollArea {
    border: none;
    background: transparent;
    background-color: transparent;
}

QScrollArea > .QWidget {
    background: transparent;
    border: none;
}

QScrollArea > .QWidget > .QWidget {
    background: transparent;
    border: none;
}

QScrollBar:vertical {
    width: 6px;
    background: transparent;
    margin: 0;
}

QScrollBar::handle:vertical {
    background-color: rgba(255, 255, 255, 0.16);
    border-radius: 3px;
    min-height: 36px;
}

QScrollBar::handle:vertical:hover {
    background-color: rgba(255, 255, 255, 0.3);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}

QScrollBar:horizontal {
    height: 0px;
    background: transparent;
}

/* ==========================================================================
   macOS Dock Control Bar & Feedback
   ========================================================================== */
#controlBar {
    background-color: rgba(30, 30, 32, 0.94);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 8px 16px;
}

#feedback {
    background: transparent;
    border: none;
    color: #98989d;
    font-size: 12px;
    font-weight: 400;
    padding: 0 4px;
}

/* Inset Grouped List Styles */
#settingsRow {
    background: transparent;
    border: none;
}

#rowTitle {
    font-size: 13px;
    font-weight: 600;
    color: #f5f5f7;
}

#rowSubtitle {
    font-size: 11.5px;
    color: #86868b;
}

/* Preset Cards */
.presetCard {
    background-color: rgba(255, 255, 255, 0.04);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    padding: 10px;
}

.presetCard:hover {
    border-color: rgba(255, 255, 255, 0.2);
    background-color: rgba(255, 255, 255, 0.07);
}
'''.replace('__CHECK_ICON__', CHECK_ICON_PATH)


def initialize_fonts():
    # The offscreen Qt platform has no system font database on Windows.
    # Read the user's installed fonts for checks; never redistribute them.
    if not QFontDatabase.families():
        fonts = Path(os.environ.get('SystemRoot', 'C:/Windows')) / 'Fonts'
        for filename in ('msyh.ttc', 'msyhbd.ttc', 'segoeui.ttf', 'segoeuib.ttf', 'seguiemj.ttf', 'seguisym.ttf'):
            path = fonts / filename
            if path.is_file():
                QFontDatabase.addApplicationFont(str(path))


def card(title, description=None):
    frame = QFrame()
    frame.setObjectName('card')
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 11, 16, 11)
    layout.setSpacing(6)
    label = QLabel(title)
    label.setObjectName('sectionTitle')
    layout.addWidget(label)
    if description:
        desc_label = QLabel(description)
        desc_label.setObjectName('muted')
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
    return frame, layout


class HairlineDivider(QFrame):
    """Subtle horizontal separator between Inset Grouped items."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(1)
        self.setStyleSheet('background-color: rgba(255, 255, 255, 0.06); border: none;')


class SettingsRow(QFrame):
    """macOS Inset Grouped List single row with title, description, and control widget."""
    def __init__(self, title, subtitle=None, widget=None, parent=None):
        super().__init__(parent)
        self.setObjectName('settingsRow')
        self.setStyleSheet('QFrame#settingsRow { background: transparent; border: none; }')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 4, 2, 4)
        layout.setSpacing(14)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        title_lbl = QLabel(title)
        title_lbl.setObjectName('rowTitle')
        title_lbl.setStyleSheet('color: #f5f5f7; font-weight: 600; font-size: 13px;')
        text_layout.addWidget(title_lbl)

        if subtitle:
            sub_lbl = QLabel(subtitle)
            sub_lbl.setObjectName('rowSubtitle')
            sub_lbl.setStyleSheet('color: #86868b; font-size: 11.5px;')
            sub_lbl.setWordWrap(True)
            text_layout.addWidget(sub_lbl)

        layout.addLayout(text_layout, 1)

        if widget:
            layout.addWidget(widget, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)


class MacSwitch(QCheckBox):
    """Authentic Apple macOS Sequoia Capsule Toggle Switch."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(38, 22)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        checked = self.isChecked()
        w = float(self.width())
        h = float(self.height())
        radius = h / 2.0

        # Background track
        if checked:
            track_color = QColor('#34c759')  # Apple Green
            border_color = QColor('#34c759')
        else:
            track_color = QColor(255, 255, 255, 38)
            border_color = QColor(255, 255, 255, 28)

        track_rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        painter.setPen(QPen(border_color, 1.0))
        painter.setBrush(track_color)
        painter.drawRoundedRect(track_rect, radius, radius)

        # White circle knob (thumb)
        knob_dia = h - 4.0
        knob_y = 2.0
        knob_x = (w - knob_dia - 2.0) if checked else 2.0

        # Subtle shadow under knob
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 45))
        painter.drawEllipse(QRectF(knob_x, knob_y + 1.0, knob_dia, knob_dia))

        # Knob body
        painter.setBrush(QColor('#ffffff'))
        painter.drawEllipse(QRectF(knob_x, knob_y, knob_dia, knob_dia))
        painter.end()

