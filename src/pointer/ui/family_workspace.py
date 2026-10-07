"""Cursor family workspace; observation state never enters CursorSettings."""
from dataclasses import replace
import re

from PySide6.QtCore import Qt, QTimer, QSize, QRectF, QEvent, Signal
from PySide6.QtGui import QImage, QPixmap, QIcon, QPainter, QColor, QPen, QPainterPath
from PySide6.QtWidgets import (
    QWidget, QFrame, QLabel, QPushButton, QComboBox, QVBoxLayout,
    QHBoxLayout, QGridLayout, QButtonGroup, QToolButton, QLineEdit, QLayout,
)
from pointer.cursor.resources import RenderRequest, render_cursor, DPI_VARIANTS
from pointer.cursor.motion import ClickMotion
from pointer.cursor.art.catalog import RENDERERS
from .preview import PreviewPanel, PreviewSurface
from .pages.appearance import AppearancePage, PRESETS, WORKSPACE_PRESETS
from .theme import MacSwitch
from .colors import theme_colors, widget_colors
from .input_controls import ChoiceComboBox

ROLE_LABELS = {
    'arrow': '箭头', 'hand': '手形', 'ibeam': '输入', 'busy': '加载',
    'working': '后台运行', 'move': '移动', 'crosshair': '精确选择',
    'help': '帮助', 'no': '不可用', 'ns': '垂直调整',
    'ew': '水平调整', 'nwse': '对角调整 ↘', 'nesw': '对角调整 ↗',
    'up': '向上箭头', 'pen': '手写', 'pin': '位置选择', 'person': '人员选择',
}


def navigation_icon(index, dark, dpr):
    canvas = QPixmap(round(24*dpr), round(24*dpr))
    canvas.setDevicePixelRatio(dpr)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(theme_colors(dark)['text']), 1.5))
    if index == 0:
        path = QPainterPath()
        path.moveTo(4, 3)
        for x, y in ((20, 9), (12, 12), (9, 21)):
            path.lineTo(x, y)
        path.closeSubpath()
        painter.drawPath(path)
    elif index == 1:
        for y in (8, 16):
            path = QPainterPath()
            path.moveTo(3, y)
            path.cubicTo(8, y-8, 16, y+8, 21, y)
            painter.drawPath(path)
    elif index == 2:
        painter.drawEllipse(6, 6, 12, 12)
        for x1, y1, x2, y2 in ((12, 2, 12, 9), (12, 15, 12, 22), (2, 12, 9, 12), (15, 12, 22, 12)):
            painter.drawLine(x1, y1, x2, y2)
    else:
        for y, x in ((5, 8), (12, 16), (19, 10)):
            painter.drawLine(3, y, 21, y)
            painter.setBrush(QColor(theme_colors(dark)['canvas']))
            painter.drawEllipse(x-2, y-2, 4, 4)
    painter.end()
    icon = QIcon(canvas)
    selected = canvas.copy()
    painter = QPainter(selected)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(selected.rect(), QColor(theme_colors(dark)['selected_text']))
    painter.end()
    icon.addPixmap(selected, QIcon.Mode.Normal, QIcon.State.On)
    return icon


def cursor_pixmap(settings, role, theme, frame=0, crop=True, dpi=96):
    image, _ = render_cursor(RenderRequest(settings, role, theme, frame, dpi))
    if crop:
        # Keep the same origin during motion; per-frame bounds cancel translation.
        neutral = image if frame == 0 else render_cursor(RenderRequest(settings, role, theme, 0, dpi))[0]
        bounds = neutral.getchannel('A').getbbox()
        if bounds:
            margin = max(4, round(settings.size * dpi / 96 * .2))
            image = image.crop((max(0, bounds[0] - margin), max(0, bounds[1] - margin),
                                min(image.width, bounds[2] + margin), min(image.height, bounds[3] + margin)))
    data = image.tobytes('raw', 'RGBA')
    return QPixmap.fromImage(QImage(data, image.width, image.height, QImage.Format.Format_RGBA8888).copy())


def specimen_icon(settings, role, theme):
    image, _ = render_cursor(RenderRequest(replace(settings, size=64), role, theme))
    image = image.crop(image.getchannel('A').getbbox())
    data = image.tobytes('raw', 'RGBA')
    source = QPixmap.fromImage(QImage(data, image.width, image.height, QImage.Format.Format_RGBA8888).copy())
    height = {'arrow': 40, 'hand': 40, 'ibeam': 38, 'busy': 36, 'move': 38}.get(role, 40)
    fitted = source.scaled(44, height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    canvas = QPixmap(52, 48)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    painter.drawPixmap((52 - fitted.width()) // 2, (48 - fitted.height()) // 2, fitted)
    painter.end()
    return QIcon(canvas)


class FamilyComboBox(ChoiceComboBox):
    """Keep the native combo menu while drawing a theme-readable disclosure."""
    def __init__(self):
        super().__init__()
        self.setProperty('familyCombo', True)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colors = widget_colors(self)
        pen = QPen(QColor(colors['text'] if self.isEnabled() else colors['disabled_text']), 1.6)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        x, y = self.width() - 16, self.height() // 2
        painter.drawLine(x - 4, y - 2, x, y + 2)
        painter.drawLine(x, y + 2, x + 4, y - 2)


def segmented_combo(combo, labels):
    """Native backing model, explicit nearby choices without wheel value edits."""
    widget = QWidget()
    combo.setParent(widget)
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)
    group = QButtonGroup(widget)
    buttons = []
    for index, label in enumerate(labels):
        button = QToolButton()
        button.setText(label)
        button.setProperty('segmented', True)
        button.setCheckable(True)
        button.setMinimumHeight(36)
        button.setMinimumWidth(button.fontMetrics().horizontalAdvance(label) + 16)
        button.setToolTip(combo.itemText(index))
        button.setAccessibleName(combo.accessibleName() + ' ' + label)
        button.clicked.connect(lambda checked=False, index=index: combo.setCurrentIndex(index))
        group.addButton(button)
        layout.addWidget(button, 1)
        buttons.append(button)
    def sync():
        for index, button in enumerate(buttons):
            button.setChecked(index == combo.currentIndex())
    combo.currentIndexChanged.connect(sync)
    combo.hide()
    combo.choice_buttons = buttons
    sync()
    widget.buttons = buttons
    return widget


def family_specimen_icon(settings, style, theme, dpr):
    canvas = QPixmap(round(48*dpr), round(42*dpr))
    canvas.setDevicePixelRatio(dpr)
    canvas.fill(Qt.GlobalColor.transparent)
    painter = QPainter(canvas)
    for role, x, y, width, height in (('arrow', 0, 5, 28, 32), ('hand', 29, 0, 18, 20), ('ibeam', 30, 22, 16, 18)):
        image = cursor_pixmap(replace(settings, style=style, size=32), role, theme,
                              dpi=192 if dpr > 1 else 96)
        fitted = image.scaled(round(width*dpr), round(height*dpr), Qt.AspectRatioMode.KeepAspectRatio,
                              Qt.TransformationMode.SmoothTransformation)
        fitted.setDevicePixelRatio(dpr)
        painter.drawPixmap(x, y, fitted)
    painter.end()
    return QIcon(canvas)


class FamilySurface(PreviewSurface):
    def __init__(self, owner, theme, hero=False, actual=False):
        super().__init__(owner, theme)
        self.hero, self.actual = hero, actual
        self.setMinimumHeight(60 if actual else 200 if hero else 100)
        self.setMinimumWidth(70)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName('实际大小光标' if actual else '草稿光标预览，按住查看动效')

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            if not event.isAutoRepeat():
                self.setProperty('keyboardFocus', True)
                self.pressed = True
                self.owner.set_down(True)
                self.update()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            if not event.isAutoRepeat():
                self.release_preview_press()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def release_preview_press(self):
        self.pressed = False
        self.owner.set_down(False)
        self.update()

    def event(self, event):
        if event.type() in (QEvent.Type.FocusOut, QEvent.Type.Hide, QEvent.Type.WindowDeactivate, QEvent.Type.UngrabMouse):
            self.release_preview_press()
        return super().event(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = self.owner.ui_theme if self.hero else self.theme
        if not self.hero:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#f0f1f5' if theme == 'light' else '#25262b'))
            painter.drawRoundedRect(QRectF(self.rect()), 16, 16)
            painter.setPen(QColor('#5d5f68' if theme == 'light' else '#b2b5c0'))
            painter.drawText(self.rect().adjusted(8, 12, -8, -8), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                             '浅色背景' if theme == 'light' else '深色背景')
        if self.actual:
            # A compact real-size sample lives in a task context, not a blank poster.
            colors = theme_colors(theme == 'dark')
            scene = QRectF(self.width()/2-64, self.height()/2-18, 128, 34)
            painter.setBrush(QColor(colors['selected'] if self.pressed else colors['raised']))
            painter.setPen(QPen(QColor(colors['border']), 1))
            painter.drawRoundedRect(scene, 7, 7)
            painter.setPen(QColor(colors['text']))
            painter.drawText(scene.adjusted(6, 0, -8, 0), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, '按住体验' if self.pressed else '示例按钮')
        settings = self.owner.settings
        effective = settings.appearance if settings.appearance in ('light', 'dark') else theme
        role = self.owner.role.currentData() or 'arrow'
        frame = self.owner.frame if role in ('arrow', 'hand') else self.owner.loading_frame if role in ('busy', 'working') else 0
        # Render enlarged specimens at a supported canonical size before scaling.
        rendered = settings if self.actual else replace(settings, size=64)
        dpi = min(DPI_VARIANTS, key=lambda value: abs(value - 96 * self.devicePixelRatioF())) if self.actual else 384
        key = (rendered, role, effective, frame, self.actual, dpi)
        pixmap = self.owner.get_cached_pixmap(key)
        if pixmap is None:
            pixmap = cursor_pixmap(rendered, role, effective, frame, crop=not self.actual, dpi=dpi)
            if self.actual:
                pixmap.setDevicePixelRatio(dpi / 96)
            self.owner.put_cached_pixmap(key, pixmap)
        if self.actual:
            logical = pixmap.deviceIndependentSize()
            x, y = (self.width() - logical.width()) / 2, (self.height() - logical.height()) / 2 + 12
            painter.drawPixmap(round(x), round(y), pixmap)
            self.cursor_bounds = QRectF(x, y, logical.width(), logical.height())
        else:
            target = max(24, min(220, self.width() - 24, self.height() - 56))
            scaled = pixmap.scaled(target, target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            x, y = (self.width() - scaled.width()) // 2, (self.height() - scaled.height()) // 2 + 12
            painter.drawPixmap(x, y, scaled)
            self.cursor_bounds = QRectF(x, y, scaled.width(), scaled.height())
        if self.hasFocus() and self.property('keyboardFocus'):
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(theme_colors(theme == 'dark')['focus']), 2))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 12, 12)
        elif self.pressed or self.hovered:
            colors = theme_colors(theme == 'dark')
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(colors['accent'] if self.pressed else colors['border']),
                                2 if self.pressed else 1))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 12, 12)


class FamilyPreviewPanel(PreviewPanel):
    def __init__(self, settings):
        QWidget.__init__(self)
        self.settings, self.frame, self.loading_frame = settings, 0, 0
        self.motion = ClickMotion(settings.press_ms, settings.release_ms, mode=settings.motion)
        self.down = False
        self._pixmap_cache = {}
        self._last_loading_time = 0.0
        self.ui_theme = 'light'
        self.setMinimumWidth(320)
        self.setObjectName('previewWorkspace')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)
        toolbar = QHBoxLayout()
        self.role = FamilyComboBox()
        self.role.setFixedWidth(90)
        self.role.setObjectName('previewRole')
        self.role.setAccessibleName('预览角色，不修改整套配置')
        self.role.setToolTip('角色仅用于预览。右侧属性应用于整套光标。')
        for role in dict.fromkeys(('arrow', 'hand', 'ibeam', 'busy', 'move', 'working', *RENDERERS)):
            self.role.addItem(ROLE_LABELS.get(role, role), role)
        toolbar.addWidget(self.role, 2, Qt.AlignmentFlag.AlignBottom)
        self.background = FamilyComboBox()
        self.background.setObjectName('previewBackground')
        self.background.setAccessibleName('预览背景')
        for label, value in [('浅背景', 'light'), ('深背景', 'dark'), ('双背景', 'compare')]:
            self.background.addItem(label, value)
        self.background.setCurrentIndex(2)
        toolbar.addWidget(self.background, 1)
        self.scale = FamilyComboBox()
        self.scale.setAccessibleName('预览缩放')
        self.scale.setToolTip('1:1 按逻辑像素显示完整光标画布；实际 Windows 尺寸取决于系统 DPI。')
        self.scale.addItem('放大', 'enlarged')
        self.scale.addItem('1:1', 'actual')
        toolbar.removeWidget(self.background)
        self.background_label = QLabel('预览')
        self.background_label.setObjectName('muted')
        background_group = QWidget()
        background_layout = QVBoxLayout(background_group)
        background_layout.setContentsMargins(0, 0, 0, 0)
        background_layout.setSpacing(2)
        background_layout.addWidget(self.background_label)
        background_layout.addWidget(segmented_combo(self.background, ('浅', '深', '对比')))
        toolbar.addWidget(background_group, 2)
        toolbar.addWidget(segmented_combo(self.scale, ('放大', '1:1')), 1, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(toolbar)
        self.pair_layout = QHBoxLayout()
        self.pair_layout.setSpacing(8)
        self.surfaces = [FamilySurface(self, theme) for theme in ('light', 'dark')]
        for surface in self.surfaces:
            surface.setMinimumHeight(180)
            self.pair_layout.addWidget(surface, 1)
        self.hero = self.surfaces[0]
        self.actual = self.hero
        layout.addLayout(self.pair_layout, 1)
        self.selected_label = QLabel()
        self.selected_label.setObjectName('selectedRoleLabel')
        layout.addWidget(self.selected_label)
        role_row = QHBoxLayout()
        role_row.setSpacing(4)
        self.role_buttons, self.role_slots = {}, {}
        for role in ('arrow', 'hand', 'ibeam', 'busy', 'move'):
            button = QToolButton()
            button.setText(ROLE_LABELS[role])
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setCheckable(True)
            button.setMinimumHeight(64)
            button.setIconSize(QSize(40, 36))
            button.setObjectName('roleSpecimen')
            button.setAccessibleName(ROLE_LABELS[role] + '预览')
            button.clicked.connect(lambda checked=False, role=role: self.role.setCurrentIndex(self.role.findData(role)))
            self.role_buttons[role] = button
            self.role_slots[role] = button
            role_row.addWidget(button, 1)
        layout.addLayout(role_row)
        self.actual_label = QLabel()
        self.actual_label.setObjectName('muted')
        self.actual_label.setToolTip('按住预览或使用空格体验当前草稿动效；不会更改系统光标。')
        layout.addWidget(self.actual_label)
        self.role.currentIndexChanged.connect(self.refresh)
        self.background.currentIndexChanged.connect(self.update_background)
        self.scale.currentIndexChanged.connect(self.update_background)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(self.tick)
        self.timer.start()
        self.update_background()

    def set_down(self, down):
        super().set_down(down)
        self.refresh()
        if getattr(self.window(), 'reduce_motion', False):
            # Do not retain a held animation when motion is suppressed: turning
            # it back on after cancellation must not revive the old press.
            self.motion = ClickMotion(self.settings.press_ms, self.settings.release_ms, mode=self.settings.motion)
            self.frame = 0
            self.refresh()

    def tick(self):
        if getattr(self.window(), 'reduce_motion', False):
            return
        super().tick()

    def update_background(self):
        mode = self.background.currentData()
        for surface in self.surfaces:
            surface.actual = self.scale.currentData() == 'actual'
            surface.setVisible(mode == 'compare' or mode == surface.theme)
        self.refresh()

    def clear_press(self):
        for surface in self.surfaces:
            surface.pressed = False
            surface.update()
        self.set_down(False)

    def refresh(self):
        if not hasattr(self, 'hero'):
            return
        role = self.role.currentData() or 'arrow'
        self.selected_label.setText(ROLE_LABELS.get(role, role) + (' · 按住中' if self.down else ' · 草稿预览'))
        self.actual_label.setText(f'{self.settings.size} px · ' + ('1:1 逻辑像素' if self.scale.currentData() == 'actual' else '放大观察') + ' · 按住 / 空格')
        for surface in self.surfaces:
            surface.update()
        icon_key = (self.settings.style, self.settings.light_body, self.settings.light_outline,
                    self.settings.dark_body, self.settings.dark_outline, self.settings.aura_glow,
                    self.settings.aura_color, self.ui_theme)
        if icon_key != getattr(self, '_role_icon_key', None):
            for kind, button in self.role_buttons.items():
                button.setIcon(specimen_icon(self.settings, kind, self.ui_theme))
            self._role_icon_key = icon_key
        for kind, button in self.role_buttons.items():
            button.setChecked(kind == role)


class FamilyAppearancePage(AppearancePage):
    validation_changed = Signal()

    def __init__(self, change):
        QWidget.__init__(self)
        self.setObjectName('propertyInspector')
        self.change, self.settings = change, None
        self.preset_buttons, self.trendy_preset_buttons = [], []
        self._color_original, self._base_preset = None, None
        self._preset_cache = {}
        self.invalid_fields = set()
        self.ui_theme = 'light'
        self.family_layout = QVBoxLayout(self)
        self.family_layout.setContentsMargins(16, 12, 16, 12)
        self.family_layout.setSpacing(6)
        self.preview_slot = QVBoxLayout()
        heading = QLabel('整套外观')
        heading.setObjectName('sectionTitle')
        heading.setToolTip('造型、尺寸和配色应用于全部 17 种系统光标。')
        self.family_layout.addWidget(heading)
        choices = QGridLayout()
        choices.setSpacing(4)
        self.shape_buttons = {}
        self.shape_group = QButtonGroup(self)
        for index, (label, style) in enumerate([('圆润', 'sequoia'), ('细笔', 'quill'), ('切面', 'facet'),
                                              ('长矛', 'lance'), ('滴形', 'droplet'), ('直角', 'rectilinear')]):
            button = QToolButton()
            button.setText(label)
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setCheckable(True)
            button.setMinimumHeight(76)
            button.setIconSize(QSize(48, 42))
            button.setToolTip(label + ' · 箭头 / 手形 / 文本，整套角色使用同一几何语言。')
            button.clicked.connect(lambda checked=False, style=style: self.change(style=style))
            self.shape_group.addButton(button)
            self.shape_buttons[style] = button
            choices.addWidget(button, index // 3, index % 3)
        self.family_layout.addLayout(choices)
        self.legacy_style = FamilyComboBox()
        self.legacy_style.setAccessibleName('历史造型，保留已有配置')
        for label, style in [('历史 · 线框', 'outline'), ('历史 · 精准', 'precision'), ('历史 · 锐角', 'falcon'), ('历史 · 像素', 'pixel')]:
            self.legacy_style.addItem(label, style)
        self.legacy_style.currentIndexChanged.connect(lambda: self.change(style=self.legacy_style.currentData()))
        self.legacy_style.hide()
        self.legacy_toggle = QPushButton('历史造型')
        self.legacy_toggle.setObjectName('legacyToggle')
        self.legacy_toggle.setCheckable(True)
        self.legacy_toggle.setAccessibleName('展开或收起历史造型')
        self.legacy_toggle.toggled.connect(self.legacy_style.setVisible)
        self.family_layout.addWidget(self.legacy_toggle)
        self.family_layout.addWidget(self.legacy_style)
        self.family_size = FamilyComboBox()
        for size in (24, 32, 40, 48, 64):
            self.family_size.addItem(f'{size} px', size)
        self.family_size.currentIndexChanged.connect(lambda: self.change(size=self.family_size.currentData()))
        self.family_size.setAccessibleName('光标尺寸')
        self.family_appearance = FamilyComboBox()
        for label, value in [('自动', 'adaptive'), ('浅色', 'light'), ('深色', 'dark')]:
            self.family_appearance.addItem(label, value)
        self.family_appearance.setToolTip('自动根据背景切换；固定模式使用所选颜色通道。此项修改系统配置草稿。')
        self.family_appearance.currentIndexChanged.connect(lambda: self.change(appearance=self.family_appearance.currentData()))
        self.family_appearance.setAccessibleName('系统背景适配')
        size_choices = segmented_combo(self.family_size, ('24', '32', '40', '48', '64'))
        appearance_choices = segmented_combo(self.family_appearance, ('自动', '浅色', '深色'))
        for title, control in [('尺寸 · px', size_choices), ('背景适配', appearance_choices)]:
            row = QVBoxLayout()
            row.setSpacing(4)
            row.addWidget(QLabel(title))
            row.addWidget(control)
            self.family_layout.addLayout(row)
        palette_heading = QHBoxLayout()
        palette_heading.addWidget(QLabel('配色'))
        self.palette_name = QLabel()
        self.palette_name.setObjectName('muted')
        self.palette_name.setWordWrap(True)
        palette_heading.addWidget(self.palette_name, 1)
        self.reset_palette = QPushButton('重置配色')
        self.reset_palette.setObjectName('compactAction')
        self.reset_palette.clicked.connect(self.restore_palette)
        palette_heading.addWidget(self.reset_palette)
        self.family_layout.addLayout(palette_heading)
        self.names = {'classic': '黑白', 'aurora': '极光', 'obsidian': '暖金', 'geek': '高对比',
                      'cyber': '霓虹', 'mist': '莫兰迪', 'sakura': '樱花', 'abyssal': '深海',
                      'slate': '雾蓝', 'stone': '暖灰', 'sage': '鼠尾草', 'clay': '陶土',
                      'mauve': '灰紫', 'ocean': '深海', 'rose': '烟粉'}
        self.preset_grid = QGridLayout()
        self.preset_grid.setSpacing(6)
        for index, preset in enumerate(WORKSPACE_PRESETS):
            button = QToolButton()
            button.setObjectName('paletteSpecimen')
            button.setText(self.names[preset['id']])
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setCheckable(True)
            button.setMinimumHeight(60)
            button.setIconSize(QSize(80, 32))
            button.setToolTip(self.names[preset['id']] + ' · 浅 / 深背景实物预览；点击仅修改配色草稿')
            button.clicked.connect(lambda checked=False, preset=preset: self.apply_preset(preset))
            target = self.preset_buttons
            target.append((button, preset))
            self.preset_grid.addWidget(button, index // 2, index % 2)
        self.family_layout.addLayout(self.preset_grid)
        self.palette_button = QPushButton('自定义颜色与光晕')
        self.palette_button.setCheckable(True)
        self.palette_button.clicked.connect(self.open_advanced)
        self.family_layout.addWidget(self.palette_button)
        self.inline_colors = QWidget()
        custom = QVBoxLayout(self.inline_colors)
        custom.setContentsMargins(0, 4, 0, 0)
        custom.setSpacing(8)
        self.color_previews = {}
        self.color_fields, self.color_swatches = {}, {}
        for field, title in (('light_body', '浅色主体'), ('light_outline', '浅色描边'),
                             ('dark_body', '深色主体'), ('dark_outline', '深色描边')):
            custom.addWidget(self.make_color_field(field, title))
        glow_row = QHBoxLayout()
        glow_row.addWidget(QLabel('光晕'), 1)
        self.aura_glow = MacSwitch()
        self.aura_glow.setAccessibleName('光晕开关，修改草稿')
        self.aura_glow.toggled.connect(lambda enabled: self.change(aura_glow=enabled))
        glow_row.addWidget(self.aura_glow)
        custom.addLayout(glow_row)
        custom.addWidget(self.make_color_field('aura_color', '光晕颜色'))
        self.color_error = QLabel('HEX / RGB · 仅修改草稿')
        self.color_error.setObjectName('colorHint')
        self.color_error.setWordWrap(True)
        custom.addWidget(self.color_error)
        self.cancel_colors = QPushButton('撤销本次颜色编辑')
        self.cancel_colors.clicked.connect(self.cancel_color_edit)
        custom.addWidget(self.cancel_colors)
        self.inline_colors.hide()
        self.family_layout.addWidget(self.inline_colors)
        self.family_layout.addStretch()
        self.family_layout.setSizeConstraint(QLayout.SizeConstraint.SetMinimumSize)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Three curated specimens fit in 326px including control padding/margins.
        columns = getattr(self, '_reference_palette_columns', 3 if self.width() >= 326 else 1)
        if columns != getattr(self, '_preset_columns', None):
            for index, (button, _) in enumerate(self.preset_buttons + self.trendy_preset_buttons):
                self.preset_grid.removeWidget(button)
                self.preset_grid.addWidget(button, index // columns, index % columns)
            self._preset_columns = columns
            self.preset_grid.invalidate()
            self.family_layout.invalidate()
            self.updateGeometry()

    @staticmethod
    def preset_fields(preset):
        return {key: preset[key] for key in ('light_body', 'light_outline', 'dark_body', 'dark_outline')}

    def apply_preset(self, preset):
        self._base_preset = preset['id']
        self.invalid_fields.clear()
        for field, edit in self.color_fields.items():
            edit.setProperty('invalid', False)
            edit.setText(self.preset_fields(preset).get(field, '#007aff'))
        self.change(**self.preset_fields(preset))

    def restore_palette(self):
        preset = next((p for p in (*WORKSPACE_PRESETS, *PRESETS) if p['id'] == self._base_preset), PRESETS[0])
        self.apply_preset(preset)

    def preset_icon(self, settings, preset, checked):
        dpr = self.devicePixelRatioF()
        key = (settings.style, preset['id'], settings.appearance, settings.aura_glow,
               settings.aura_color, dpr, checked, self.ui_theme)
        if key in self._preset_cache:
            return self._preset_cache[key]
        sample = replace(settings, size=32, **self.preset_fields(preset))
        pixmap = QPixmap(round(80 * dpr), round(32 * dpr))
        pixmap.setDevicePixelRatio(dpr)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        for offset, theme in ((0, 'light'), (42, 'dark')):
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor('#f0f1f5' if theme == 'light' else '#25262b'))
            painter.drawRoundedRect(QRectF(offset, 0, 38, 32), 5, 5)
            image = cursor_pixmap(sample, 'arrow', theme, dpi=192 if dpr > 1 else 96)
            fitted = image.scaled(round(24 * dpr), round(28 * dpr), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            fitted.setDevicePixelRatio(dpr)
            painter.drawPixmap(offset + (38 - round(fitted.deviceIndependentSize().width())) // 2, 2, fitted)
        if checked:
            pen = QPen(QColor('#a9ceff'), 1.8)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(pen)
            painter.drawLine(65, 6, 68, 9)
            painter.drawLine(68, 9, 73, 4)
        painter.end()
        icon = QIcon(pixmap)
        if len(self._preset_cache) > 128:
            self._preset_cache.clear()
        self._preset_cache[key] = icon
        return icon

    def make_color_field(self, field, title):
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(QLabel(title))
        swatch = QPushButton()
        swatch.setFixedSize(32, 32)
        swatch.setAccessibleName(title + '色样，定位颜色输入')
        layout.addWidget(swatch)
        edit = QLineEdit()
        edit.setObjectName('customColor_' + field)
        edit.setAccessibleName(title + '，HEX 或 RGB')
        edit.setMinimumWidth(120)
        edit.setPlaceholderText('#RRGGBB / rgb(r,g,b)')
        edit.textEdited.connect(lambda text, field=field: self.edit_color(field, text, report_error=False))
        edit.editingFinished.connect(lambda field=field, edit=edit: self.edit_color(field, edit.text()))
        swatch.clicked.connect(lambda checked=False, edit=edit: edit.setFocus(Qt.FocusReason.OtherFocusReason))
        layout.addWidget(edit, 1)
        self.color_fields[field], self.color_swatches[field] = edit, swatch
        return row

    def edit_color(self, field, text, report_error=True):
        value = text.strip()
        if re.fullmatch(r'#[0-9a-fA-F]{6}', value):
            color = value.lower()
        else:
            rgb_text = value[4:-1] if value.startswith('rgb(') and value.endswith(')') else value
            match = re.fullmatch(r'\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*', rgb_text)
            rgb = tuple(map(int, match.groups())) if match else ()
            color = '#%02x%02x%02x' % rgb if rgb and max(rgb) <= 255 else None
        if color is None:
            if not report_error:
                return
            self.invalid_fields.add(field)
            self.color_fields[field].setProperty('invalid', True)
            self.color_fields[field].style().unpolish(self.color_fields[field])
            self.color_fields[field].style().polish(self.color_fields[field])
            self.color_error.setText('颜色格式无效：请输入 #RRGGBB 或三个 0–255 的 RGB 数值。草稿未改变。')
            self.color_error.setProperty('error', True)
            self.color_error.style().unpolish(self.color_error)
            self.color_error.style().polish(self.color_error)
            self.validation_changed.emit()
            return
        self.invalid_fields.discard(field)
        self.color_fields[field].setProperty('invalid', False)
        self.color_fields[field].style().unpolish(self.color_fields[field])
        self.color_fields[field].style().polish(self.color_fields[field])
        self.color_error.setText('颜色已更新草稿；点击“应用更改”后生效。')
        self.color_error.setProperty('error', False)
        self.color_error.style().unpolish(self.color_error)
        self.color_error.style().polish(self.color_error)
        self.change(**{field: color})

    def cancel_color_edit(self):
        if self._color_original:
            self.change(**self._color_original)
        self.reset_color_session()

    def reset_color_session(self):
        self._color_original = None
        self.invalid_fields.clear()
        for edit in self.color_fields.values():
            edit.setProperty('invalid', False)
        # Hiding a focused editor emits editingFinished; stale input must not
        # overwrite a just-applied or restored draft during that transition.
        for edit in self.color_fields.values():
            edit.blockSignals(True)
        self.inline_colors.hide()
        for edit in self.color_fields.values():
            edit.blockSignals(False)
        self.palette_button.setChecked(False)
        self.validation_changed.emit()

    def open_advanced(self):
        opening = self.inline_colors.isHidden()
        if opening and self.settings:
            self._color_original = {key: getattr(self.settings, key) for key in (*self.color_fields, 'aura_glow')}
        self.inline_colors.setVisible(opening)
        self.palette_button.setChecked(opening)
        if opening:
            QTimer.singleShot(0, self.reveal_colors)

    def reveal_colors(self):
        if self.inline_colors.isHidden():
            return
        self.color_fields['light_body'].setFocus(Qt.FocusReason.OtherFocusReason)
        parent = self.parentWidget()
        while parent and not hasattr(parent, 'ensureWidgetVisible'):
            parent = parent.parentWidget()
        if parent:
            parent.ensureWidgetVisible(self.inline_colors)

    def attach_preview(self, preview):
        self.preview_slot.addWidget(preview)

    def sync(self, settings):
        self.settings = settings
        if not hasattr(self, 'shape_buttons'):
            return
        for combo, value in [(self.family_size, settings.size), (self.family_appearance, settings.appearance)]:
            combo.blockSignals(True)
            combo.setCurrentIndex(combo.findData(value))
            combo.blockSignals(False)
            for index, button in enumerate(getattr(combo, 'choice_buttons', ())):
                button.setChecked(index == combo.currentIndex())
        for style, button in self.shape_buttons.items():
            button.setChecked(style == settings.style)
        shape_key = (settings.light_body, settings.light_outline, settings.dark_body, settings.dark_outline,
                     settings.aura_glow, settings.aura_color, self.ui_theme, self.devicePixelRatioF())
        if shape_key != getattr(self, '_shape_icon_key', None):
            for style, button in self.shape_buttons.items():
                button.setIcon(family_specimen_icon(settings, style, self.ui_theme, self.devicePixelRatioF()))
            self._shape_icon_key = shape_key
        self.legacy_style.blockSignals(True)
        self.legacy_style.setCurrentIndex(self.legacy_style.findData(settings.style))
        if settings.style in ('outline', 'precision', 'falcon', 'pixel') and settings.style != getattr(self, '_last_legacy_style', None):
            self.legacy_toggle.setChecked(True)
        self._last_legacy_style = settings.style
        self.legacy_style.setVisible(self.legacy_toggle.isChecked())
        self.legacy_style.blockSignals(False)
        matched = None
        for button, preset in self.preset_buttons + self.trendy_preset_buttons:
            checked = all(getattr(settings, field) == value for field, value in self.preset_fields(preset).items())
            button.setChecked(checked)
            button.setIcon(self.preset_icon(settings, preset, checked))
            if checked:
                matched = preset['id']
        if matched:
            self._base_preset = matched
            self.palette_name.setText(self.names[matched])
        else:
            legacy = next((p for p in PRESETS[1:] if all(getattr(settings, f) == v for f, v in self.preset_fields(p).items())), None)
            if legacy:
                self._base_preset = legacy['id']
                self.palette_name.setText('历史配色 · ' + self.names[legacy['id']])
            else:
                self.palette_name.setText('自定义' + (' · 基于' + self.names[self._base_preset] if self._base_preset else ''))
        for field, edit in self.color_fields.items():
            if not edit.hasFocus() or self.inline_colors.isHidden():
                edit.setText(getattr(settings, field))
            self.color_swatches[field].setStyleSheet(f'background: {getattr(settings, field)}; border: 1px solid #858b98; border-radius: 8px;')
        self.aura_glow.blockSignals(True)
        self.aura_glow.setChecked(settings.aura_glow)
        self.aura_glow.blockSignals(False)
        for theme, label in self.color_previews.items():
            pixmap = cursor_pixmap(replace(settings, size=32), 'arrow', theme).scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            label.setPixmap(pixmap)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)


def workspace_style(dark=False):
    c = theme_colors(dark)
    return f"""
    QWidget {{ font-family: "Segoe UI", "Microsoft YaHei UI"; font-size: 14px; color: {c['text']}; }}
    QMainWindow, #rootWidget {{ background: {c['canvas']}; }}
    #content, #bannerBar, QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    #previewWorkspace, #propertyInspector {{ background: {c['surface']}; border: none; border-radius: 12px; }}
    #compactAction {{ color: {c['accent']}; background: transparent; padding: 3px 6px; font-size: 12px; }}
    #paletteSpecimen {{ padding: 3px 6px; }}
    #feedback[error="true"] {{ color: {c['danger']}; }}
    #topHeader {{ background: {c['canvas']}; border: none; }}
    #brandTitle {{ color: {c['text']}; font-size: 18px; }}
    #brandBadge, #headerVersion, #updateStatusLabel {{ color: {c['muted']}; background: transparent; }}
    #headerStatusChip {{ background: {c['raised']}; border: none; border-radius: 12px; }}
    #navCapsule, #controlBar, #familyCard, QFrame#card {{ background: {c['surface']}; border: none; border-radius: 16px; }}
    #navCapsule {{ border-radius: 12px; background: {c['raised']}; }}
    #navCapsule QPushButton {{ color: {c['text']}; background: transparent; border: 1px solid transparent; border-radius: 9px; padding: 0 12px; font-size: 14px; }}
    #navCapsule QPushButton:hover {{ color: {c['text']}; background: {c['surface']}; }}
    #navCapsule QPushButton:checked {{ color: {c['selected_text']}; background: {c['selected']}; }}
    #navCapsule QPushButton[keyboardFocus="true"]:focus {{ border: 2px solid {c['focus']}; }}
    #pageTitle {{ font-size: 22px; color: {c['text']}; font-weight: 600; }}
    #subtitle, #feedback, #rowSubtitle, #muted, #description, #tileSubtitle, #colorHint {{ color: {c['muted']}; font-size: 13px; }}
    #sectionTitle {{ color: {c['text']}; font-size: 16px; font-weight: 600; }}
    #rowTitle, #tileTitle {{ color: {c['text']}; font-size: 14px; font-weight: 600; }}
    #hairlineDivider {{ background: {c['divider']}; border: none; }}
    QLabel {{ background: transparent; }}
    QPushButton {{ color: {c['text']}; background: {c['raised']}; border: 1px solid transparent; border-radius: 9px; padding: 7px 12px; min-height: 20px; }}
    QPushButton:hover {{ color: {c['text']}; background: {c['surface']}; border-color: {c['border']}; }}
    QPushButton:focus, QToolButton:focus {{ border: 1px solid transparent; }}
    QPushButton:pressed, QToolButton:pressed {{ background: {c['selected']}; color: {c['selected_text']}; }}
    QPushButton:checked {{ background: {c['selected']}; color: {c['selected_text']}; }}
    #legacyToggle {{ color: {c['muted']}; background: transparent; padding: 2px 4px; min-height: 20px; text-align: left; }}
    #legacyToggle:hover, #legacyToggle:checked {{ color: {c['text']}; background: {c['raised']}; }}
    #legacyToggle:pressed {{ color: {c['selected_text']}; background: {c['pressed']}; }}
    QPushButton:disabled, QToolButton:disabled {{ color: {c['disabled_text']}; background: {c['raised']}; }}
    QToolButton {{ color: {c['text']}; background: transparent; border: 1px solid transparent; border-radius: 10px; padding: 6px; }}
    QToolButton[segmented="true"] {{ padding: 6px 2px; min-width: 32px; }}
    QToolButton:hover {{ background: {c['raised']}; border-color: {c['border']}; }}
    QToolButton:checked {{ background: {c['raised']}; color: {c['accent']}; border-color: {c['accent']}; }}
    QPushButton[keyboardFocus="true"]:focus, QToolButton[keyboardFocus="true"]:focus,
    QComboBox[keyboardFocus="true"]:focus, QLineEdit[keyboardFocus="true"]:focus {{ border: 2px solid {c['focus']}; }}
    #applyButton {{ color: white; background: #0056b8; min-width: 72px; min-height: 22px; font-weight: 600; }}
    #applyButton:hover {{ color: white; background: #004895; }}
    #applyButton:disabled {{ color: {c['disabled_text']}; background: {c['raised']}; border-color: {c['border']}; }}
    #themeToggle {{ background: {c['raised']}; padding: 0 12px; border-radius: 9px; }}
    QComboBox, QLineEdit {{ color: {c['text']}; background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 7px 12px; min-height: 20px; }}
    QComboBox:focus, QLineEdit:focus {{ border: 1px solid {c['border']}; }}
    QLineEdit[invalid="true"] {{ border: 1px solid {c['danger']}; }}
    QComboBox {{ padding-right: 24px; }}
    QComboBox[familyCombo="true"]::down-arrow {{ image: none; width: 0; }}
    QComboBox QAbstractItemView {{ background: {c['surface']}; color: {c['text']}; selection-background-color: {c['selected']}; selection-color: {c['selected_text']}; }}
    #selectedRoleLabel {{ color: {c['accent']}; font-weight: 600; }}
    #colorHint[error="true"] {{ color: {c['danger']}; }}
    #navCapsule {{ background: {c['canvas']}; border-right: 1px solid {c['divider']}; border-radius: 0; }}
    #navCapsule QPushButton {{ text-align: left; padding: 0 12px; min-height: 46px; max-height: 46px; border-radius: 9px; }}
    #navCapsule QPushButton:pressed, #navCapsule QPushButton:checked:pressed,
    QPushButton:checked:pressed, QToolButton:pressed, QToolButton:checked:pressed {{ background: {c['pressed']}; color: white; }}
    #applyButton:pressed {{ background: {c['pressed']}; color: white; }}
    #restoreButton {{ color: {c['danger']}; background: {c['danger_bg']}; border: 1px solid {c['danger']}; }}
    #roleTile {{ background: {c['raised']}; border: none; border-radius: 8px; }}
    #roleTile:hover {{ border: 1px solid {c['accent']}; }}
    QSlider::groove:horizontal {{ height: 4px; background: {c['border']}; border-radius: 2px; }}
    QSlider::sub-page:horizontal {{ background: {c['accent']}; border-radius: 2px; }}
    QSlider::handle:horizontal {{ background: {c['surface']}; border: 2px solid {c['accent']}; width: 16px; height: 16px; margin: -7px 0; border-radius: 9px; }}
    """
