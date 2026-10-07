"""Precise slider values with explicit typing and generous pointer targets."""
from PySide6.QtCore import QEvent, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QAbstractSpinBox, QHBoxLayout, QStyle, QStyleOptionSlider, QWidget

from .colors import theme_colors
from .input_controls import DragSlider, TypedSpinBox


class ParameterSlider(DragSlider):
    """Paint a small thumb inside Qt's larger native drag target."""
    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._keyboard_focus = False
        self._dark = None
        self.setMinimumWidth(80)
        self.setFixedHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet('''
            QSlider::groove:horizontal { height: 4px; background: transparent; }
            QSlider::handle:horizontal {
                width: 28px; height: 28px; margin: -12px 0;
                border: none; background: transparent;
            }
        ''')

    def paintEvent(self, event):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        handle = self.style().subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                             QStyle.SubControl.SC_SliderHandle, self)
        start, end = handle.width() / 2, self.width() - handle.width() / 2
        center = QPointF(handle.center().x() + .5, self.height() / 2)
        dark = self._dark if self._dark is not None else bool(getattr(self.window(), 'ui_dark', False))
        active = QColor('#9bc2fa' if dark else '#0866d8')
        track = QColor('#656b75' if dark else '#c9ced8')
        if not self.isEnabled():
            active = track = QColor('#484d57' if dark else '#dce0e7')
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(track, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(start, center.y()), QPointF(end, center.y()))
        painter.setPen(QPen(active, 3, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(end if option.upsideDown else start, center.y()), center)
        if self.hasFocus() and self._keyboard_focus:
            painter.setPen(QPen(active, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, 12, 12)
        painter.setPen(QPen(active, 1.5))
        fill = ('#dbe8fa' if dark else '#ffffff') if self.isEnabled() else ('#717783' if dark else '#edf0f5')
        if self.isEnabled() and self.underMouse():
            fill = '#e9f2ff' if dark else '#eef5ff'
        painter.setBrush(QColor(fill))
        radius = 8.5 if self.isSliderDown() else 8
        painter.drawEllipse(center, radius, radius)

    def set_theme(self, dark):
        self._dark = dark
        self.update()

    def event(self, event):
        kind = event.type()
        if kind == QEvent.Type.FocusIn:
            self._keyboard_focus = event.reason() in (Qt.FocusReason.TabFocusReason,
                Qt.FocusReason.BacktabFocusReason, Qt.FocusReason.ShortcutFocusReason)
        elif kind == QEvent.Type.MouseButtonPress:
            self._keyboard_focus = False
        if kind in (QEvent.Type.FocusIn, QEvent.Type.FocusOut, QEvent.Type.Enter,
                    QEvent.Type.Leave, QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            self.update()
        return super().event(event)


class ParameterSpinBox(TypedSpinBox):
    def __init__(self, suffix, parent=None):
        self._active = True
        self._unit = suffix
        self._dark = None
        super().__init__(parent)
        self.setObjectName('parameterValue')
        self.setSuffix(suffix)
        self.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.setKeyboardTracking(False)
        self.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.setFixedSize(96 if suffix == ' / 255' else 88, 32)
        self.set_theme(False)

    def textFromValue(self, value):
        return super().textFromValue(value) if self._active else '未启用'

    def set_active(self, active):
        if self._active != active:
            self._active = active
            self.setSuffix(self._unit if active else '')

    def set_theme(self, dark):
        if self._dark == dark:
            return
        self._dark = dark
        c = theme_colors(dark)
        self.setStyleSheet(f'''
            QSpinBox#parameterValue {{
                background: {c['surface']}; color: {c['text']};
                border: 1px solid {c['border']}; border-radius: 6px;
                padding: 4px 6px; font-size: 13px;
            }}
            QSpinBox#parameterValue:hover:enabled, QSpinBox#parameterValue:focus {{
                border-color: {c['focus']};
            }}
            QSpinBox#parameterValue:disabled {{
                background: {c['raised']}; color: {c['disabled_text']};
            }}
            QSpinBox#parameterValue QLineEdit {{
                background: transparent; border: none; border-radius: 0;
                padding: 0; min-height: 0; color: {c['text']}; font-size: 13px;
            }}
            QSpinBox#parameterValue QLineEdit:disabled {{ color: {c['disabled_text']}; }}
        ''')


class IntegerParameter(QWidget):
    valueChanged = Signal(int)
    committed = Signal(int)

    def __init__(self, minimum, maximum, suffix, title, hint='', parent=None):
        super().__init__(parent)
        self.slider = ParameterSlider(self)
        self.editor = ParameterSpinBox(suffix, self)
        for widget in (self.slider, self.editor):
            widget.setRange(minimum, maximum)
            widget.setToolTip(hint)
        self.slider.setAccessibleName(title)
        self.editor.setAccessibleName(title + '数值，回车或离开输入框后确认')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        layout.addWidget(self.slider, 1)
        layout.addWidget(self.editor)
        self.slider.valueChanged.connect(self._from_slider)
        self.editor.valueChanged.connect(self._from_editor)
        self.slider.sliderReleased.connect(lambda: self.committed.emit(self.slider.value()))
        self.editor.editingFinished.connect(lambda: self.committed.emit(self.editor.value()))

    def _from_slider(self, value):
        blocked = self.editor.blockSignals(True)
        try:
            self.editor.setValue(value)
        finally:
            self.editor.blockSignals(blocked)
        self.valueChanged.emit(value)

    def _from_editor(self, value):
        blocked = self.slider.blockSignals(True)
        try:
            self.slider.setValue(value)
        finally:
            self.slider.blockSignals(blocked)
        self.valueChanged.emit(value)

    def sync(self, value, active=True, force=False):
        slider_blocked = self.slider.blockSignals(True)
        editor_blocked = self.editor.blockSignals(True)
        try:
            self.slider.setValue(value)
            pending = active and self.editor.hasFocus() and self.editor.lineEdit().isModified()
            self.editor.set_active(active)
            # A refresh preserves uncommitted text; a changed draft replaces it.
            if force or self.editor.value() != value or not pending:
                self.editor.setValue(value)
            self.slider.setEnabled(active)
            self.editor.setEnabled(active)
        finally:
            self.slider.blockSignals(slider_blocked)
            self.editor.blockSignals(editor_blocked)

    def set_theme(self, dark):
        self.editor.set_theme(dark)
        self.slider.set_theme(dark)
