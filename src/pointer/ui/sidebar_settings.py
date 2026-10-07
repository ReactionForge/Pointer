"""Window appearance drafts stored independently of system cursor settings."""
import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path

from PySide6.QtCore import Qt, QEvent, QPointF
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QAbstractSpinBox, QStyle, QStyleOptionSlider
from .input_controls import DragSlider, TypedSpinBox
from .reference_workspace import row, group, reference_colors
from .theme import MacSwitch


@dataclass(frozen=True)
class SidebarAppearance:
    enabled: bool = True
    dark_alpha: int = 184
    light_alpha: int = 208
    blur: int = 0

    def __post_init__(self):
        if type(self.enabled) is not bool:
            raise ValueError('enabled must be a boolean')
        for value in (self.dark_alpha, self.light_alpha):
            if type(value) is not int or not 0 <= value <= 255:
                raise ValueError('alpha must be between 0 and 255')
        if type(self.blur) is not int or not 0 <= self.blur <= 48:
            raise ValueError('blur must be between 0 and 48')


class SidebarStore:
    def __init__(self, path):
        self.path = Path(path)

    def load(self):
        try:
            if self.path.stat().st_size > 4096:
                return SidebarAppearance()
            data = json.loads(self.path.read_text(encoding='utf8'))
            return SidebarAppearance(**data)
        except (OSError, ValueError, TypeError):
            return SidebarAppearance()

    def save(self, appearance):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + '.tmp')
        temporary.write_text(json.dumps(asdict(appearance), indent=2), encoding='utf8')
        os.replace(temporary, self.path)


class SidebarSlider(DragSlider):
    """Keep Qt's generous drag target while painting a lighter thumb."""
    def __init__(self, owner):
        super().__init__(Qt.Orientation.Horizontal)
        self.owner = owner
        self.setObjectName('sidebarSlider')
        self.setFixedHeight(32)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet('''
            QSlider#sidebarSlider::groove:horizontal { height: 4px; }
            QSlider#sidebarSlider::handle:horizontal {
                width: 28px; height: 28px; margin: -12px 0;
                border: none; background: transparent;
            }
        ''')

    def paintEvent(self, event):
        option = QStyleOptionSlider()
        self.initStyleOption(option)
        style = self.style()
        handle = style.subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                      QStyle.SubControl.SC_SliderHandle, self)
        length = handle.width()
        start, end = length / 2, self.width() - length / 2
        center = QPointF(handle.center().x() + .5, self.height() / 2)
        dark = self.owner.ui_dark
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
        if self.hasFocus() and self.property('keyboardFocus'):
            painter.setPen(QPen(active, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(center, 12, 12)
        painter.setPen(QPen(active if self.isEnabled() else track, 1.5))
        painter.setBrush(QColor(('#dbe8fa' if dark else '#ffffff') if self.isEnabled()
                               else ('#717783' if dark else '#edf0f5')))
        radius = 8.5 if self.isSliderDown() else 8
        painter.drawEllipse(center, radius, radius)

    def event(self, event):
        if event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut,
                            QEvent.Type.Enter, QEvent.Type.Leave):
            self.update()
        return super().event(event)


class BlurValueSpinBox(TypedSpinBox):
    def __init__(self):
        self._available = True
        super().__init__()

    def textFromValue(self, value):
        return super().textFromValue(value) if self._available else '未启用'

    def set_available(self, available):
        if self._available != available:
            self._available = available
            self.lineEdit().setText(self.textFromValue(self.value()))


class SidebarControls(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.enabled = MacSwitch()
        self.enabled.setAccessibleName('侧栏透明，仅更改此窗口外观')
        self.enabled.toggled.connect(owner.set_sidebar_transparent)
        self.transparency = SidebarSlider(owner)
        self.transparency.setRange(0, 255)
        self.transparency.setAccessibleName('侧栏透明度')
        self.transparency.valueChanged.connect(owner.set_sidebar_transparency)
        self.transparency_value = TypedSpinBox()
        self.transparency_value.setObjectName('transparency_value')
        self.transparency_value.setRange(0, 100)
        self.transparency_value.setSuffix('%')
        self.transparency_value.setAccessibleName('侧栏透明度百分比，回车或离开输入框后预览')
        self.transparency_value.valueChanged.connect(
            lambda percent: owner.set_sidebar_transparency(round(percent * 255 / 100)))
        self.blur = SidebarSlider(owner)
        self.blur.setRange(0, 48)
        self.blur.setAccessibleName('背景模糊')
        self.blur.setEnabled(False)
        self.blur.setToolTip('0 关闭背景模糊；数值越大，背景越模糊，文字与图标保持清晰。')
        self.blur.valueChanged.connect(owner.set_sidebar_blur)
        self.blur_value = BlurValueSpinBox()
        self.blur_value.setObjectName('blur_value')
        self.blur_value.setRange(0, 48)
        self.blur_value.setToolTip(self.blur.toolTip())
        self.blur_value.valueChanged.connect(owner.set_sidebar_blur)
        group(layout, '侧栏外观', [row('透明效果', self.enabled),
            row('透明度', self._value_row(self.transparency, self.transparency_value)),
            row('背景模糊', self._value_row(self.blur, self.blur_value))])
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setObjectName('referenceNote')
        layout.addWidget(self.status)
        actions = QHBoxLayout()
        actions.setContentsMargins(12, 0, 12, 4)
        actions.addStretch()
        self.cancel = QPushButton('取消预览')
        self.cancel.setAccessibleName('取消侧栏外观预览，恢复上次保存的设置')
        self.cancel.clicked.connect(owner.cancel_sidebar_settings)
        self.save = QPushButton('保存外观')
        self.save.setAccessibleName('保存侧栏外观，重启预览后恢复')
        self.save.clicked.connect(owner.save_sidebar_settings)
        actions.addWidget(self.cancel)
        actions.addWidget(self.save)
        layout.addLayout(actions)
        self._number_theme = None

    @staticmethod
    def _value_row(slider, editor):
        box = QWidget()
        box.setFixedWidth(200)
        editor.setFixedSize(68, 30)
        editor.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        editor.setKeyboardTracking(False)
        editor.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        line = QHBoxLayout(box)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(12)
        line.addWidget(slider, 1)
        line.addWidget(editor)
        return box

    @staticmethod
    def _sync_editor(editor, value, enabled, available=None):
        blocked = editor.blockSignals(True)
        try:
            if available is not None:
                editor.set_available(available)
            # Status refreshes must preserve a pending edit until its commit.
            pending = enabled and editor.hasFocus() and editor.lineEdit().isModified()
            if editor.value() != value or not pending:
                editor.setValue(value)
            editor.setEnabled(enabled)
        finally:
            editor.blockSignals(blocked)

    def _sync_number_style(self):
        if self._number_theme == self.owner.ui_dark:
            return
        self._number_theme = self.owner.ui_dark
        c = reference_colors(self.owner.ui_dark)
        self.setStyleSheet(f'''
            QSpinBox#transparency_value, QSpinBox#blur_value {{
                background: {c['surface']}; color: {c['text']};
                border: 1px solid {c['border']}; border-radius: 6px;
                padding: 4px 6px; font-size: 14px;
            }}
            QSpinBox#transparency_value:focus, QSpinBox#blur_value:focus {{
                border-color: {c['focus']};
            }}
            QSpinBox#transparency_value:disabled, QSpinBox#blur_value:disabled {{
                background: {c['raised']}; color: {c['muted']};
            }}
            QSpinBox#transparency_value QLineEdit, QSpinBox#blur_value QLineEdit {{
                background: transparent; border: none; border-radius: 0;
                padding: 0; color: {c['text']}; font-size: 14px;
            }}
            QSpinBox#transparency_value QLineEdit:disabled,
            QSpinBox#blur_value QLineEdit:disabled {{ color: {c['muted']}; }}
        ''')

    def sync(self):
        owner = self.owner
        setting = owner.sidebar_appearance
        supported = owner.material_policy['supported']
        for control, value in ((self.enabled, setting.enabled),
            (self.transparency, 255 - (setting.dark_alpha if owner.ui_dark else setting.light_alpha)),
            (self.blur, setting.blur)):
            control.blockSignals(True)
            control.setChecked(value) if control is self.enabled else control.setValue(value)
            control.blockSignals(False)
        self.enabled.setEnabled(supported)
        self.transparency.setEnabled(supported and setting.enabled)
        available = owner.blur_available
        self.blur.setEnabled(available and supported and setting.enabled)
        self.blur.setAccessibleName('背景模糊' if available else '背景模糊，当前环境未启用')
        self._sync_editor(self.transparency_value, round(self.transparency.value() * 100 / 255),
                          supported and setting.enabled)
        self._sync_editor(self.blur_value, setting.blur, available and supported and setting.enabled,
                          available)
        self.blur_value.setAccessibleName('背景模糊数值，回车或离开输入框后预览' if available
                                          else '背景模糊，当前环境未启用')
        self.transparency_value.setToolTip('当前深色主题' if owner.ui_dark else '当前浅色主题')
        self._sync_number_style()
        self.cancel.setEnabled(owner.sidebar_dirty)
        self.save.setEnabled(owner.sidebar_dirty and owner.sidebar_store is not None)
        message = '实时预览 · 透明度与模糊度独立保存，透明度按深浅主题分别记忆。' if available else '实时预览 · 透明度按深浅主题分别保存。背景模糊暂不可用。'
        self.status.setToolTip(owner.composition_error or '')
        if not supported:
            message = '当前使用不透明回退，保留已保存的透明设置。背景模糊尚未启用。'
        elif not setting.enabled:
            message = '透明已关闭。保存后重启恢复；取消可恢复上次保存的外观。'
        self.status.setText(message)
