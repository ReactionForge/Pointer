"""Two-page reference review shell. It does not replace the shipped shell yet."""
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout, QSizePolicy
from .main_window import MainWindow
from .colors import theme_colors
from .family_workspace import navigation_icon, segmented_combo
from .theme import HairlineDivider
from .pages.preferences import ThemeSelector


def reference_colors(dark):
    c = dict(theme_colors(dark))
    c.update(canvas='#242424' if dark else '#f5f5f7', surface='#2d2d2d' if dark else '#ffffff',
             raised='#353535' if dark else '#ededf0', text='#f0f0f0' if dark else '#202126',
             muted='#a0a0a0' if dark else '#60636a', border='#424242' if dark else '#d5d6da',
             divider='#404040' if dark else '#e4e5e8', selected='#0a60d8', selected_text='#ffffff',
             focus='#8abbff' if dark else '#0a60d8', on_track='#0a60d8', on_border='#8abbff' if dark else '#0a60d8')
    return c


def reference_style(dark):
    c = reference_colors(dark)
    sidebar = '#292b2e' if dark else '#e9ebef'
    return f'''
        #referenceShell, #content {{ background: {c['canvas']}; }}
        #referenceSidebar, #navCapsule {{ background: {sidebar}; border-radius: 0; }}
        #referenceSidebar {{ border-right: 1px solid {c['border']}; }}
        #referenceBrand {{ font-size: 17px; font-weight: 600; color: {c['text']}; }}
        #navCapsule QPushButton {{ min-height: 32px; max-height: 32px; padding: 4px 12px;
            border-radius: 6px; font-size: 14px; text-align: left; color: {c['text']}; }}
        #navCapsule QPushButton:checked {{ background: {c['selected']}; color: white; border: none; }}
        #navCapsule QPushButton:hover {{ background: {c['raised']}; }}
        #navCapsule QPushButton:checked:hover {{ background: #145fc4; }}
        #pageTitle {{ font-size: 15px; font-weight: 600; color: {c['text']}; }}
        #referenceGroup {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; }}
        #referenceSection {{ font-size: 12px; color: {c['muted']}; font-weight: 600; }}
        #referenceRow, #referenceRow QLabel {{ background: transparent; border: none; color: {c['text']}; font-size: 14px; }}
        #referenceRow {{ min-height: 40px; }}
        #muted, #feedback, #referenceNote {{ font-size: 12px; color: {c['muted']}; }}
        #hairlineDivider {{ background: {c['divider']}; border: none; }}
        #propertyInspector {{ background: transparent; }}
        #controlBar {{ background: {c['canvas']}; border-top: 1px solid {c['divider']}; border-radius: 0; }}
        #referencePreview {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 10px; }}
        QToolButton#shapeSpecimen {{ min-height: 44px; padding: 4px; border-radius: 6px; }}
        QToolButton#paletteSpecimen {{ min-height: 44px; padding: 4px; border-radius: 6px; }}
        QToolButton:checked {{ background: {c['raised']}; color: {c['text']}; border-color: {c['selected']}; }}
        QToolButton:pressed, QPushButton:pressed {{ background: #0053b2; color: white; }}
        #legacyToggle, #compactAction {{ color: {c['muted']}; background: transparent; font-size: 12px; }}
        #sectionTitle {{ font-size: 14px; }}
    '''


def row(title, control):
    widget = QFrame()
    widget.setObjectName('referenceRow')
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(12, 2, 12, 2)
    layout.setSpacing(12)
    label = QLabel(title)
    label.setMinimumWidth(76)
    layout.addWidget(label)
    layout.addWidget(control, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return widget


def group(layout, title, rows):
    heading = QLabel(title)
    heading.setObjectName('referenceSection')
    layout.addWidget(heading)
    frame = QFrame()
    frame.setObjectName('referenceGroup')
    inner = QVBoxLayout(frame)
    inner.setContentsMargins(0, 0, 0, 0)
    inner.setSpacing(0)
    for index, item in enumerate(rows):
        if index:
            line = HairlineDivider()
            inner.addWidget(line)
        inner.addWidget(item)
    layout.addWidget(frame)
    return frame


def controls(widgets):
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    for child in widgets:
        layout.addWidget(child)
    return widget


class ShapeGallery(QWidget):
    """Use the available width for specimens instead of a right-aligned form row."""
    def __init__(self, buttons):
        super().__init__()
        self.buttons = list(buttons)
        self.grid = QGridLayout(self)
        self.grid.setContentsMargins(10, 8, 10, 8)
        self.grid.setSpacing(6)
        self.columns = 0
        for button in self.buttons:
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setMinimumWidth(72)
            button.setFixedHeight(64)
            button.setIconSize(QSize(40, 32))
        self.reflow(6)

    def reflow(self, columns):
        if columns == self.columns:
            return
        for column in range(6):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        for index, button in enumerate(self.buttons):
            self.grid.removeWidget(button)
            self.grid.addWidget(button, index // columns, index % columns)
        self.columns = columns

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.reflow(6 if self.width() >= 560 else 3)


class ReferenceWindow(MainWindow):
    def __init__(self, application):
        self._reference_ready = False
        super().__init__(application)
        old = self.takeCentralWidget()
        self._previous_shell = old
        old.hide()
        root = QWidget()
        root.setObjectName('referenceShell')
        layout = QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName('referenceSidebar')
        sidebar.setFixedWidth(190)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 16, 0, 16)
        brand = QLabel('Pointer')
        brand.setObjectName('referenceBrand')
        brand.setContentsMargins(20, 0, 0, 10)
        side.addWidget(brand)
        self.nav_rail.setFixedWidth(190)
        side.addWidget(self.nav_rail, 1)
        for button in self.navigation:
            button.setFixedHeight(40)
            button.setIconSize(QSize(18, 18))
        self.status.setWordWrap(True)
        self.status.setContentsMargins(16, 4, 12, 4)
        side.addWidget(self.status)
        layout.addWidget(sidebar)
        editing_area = QWidget()
        editing_layout = QHBoxLayout(editing_area)
        editing_layout.setContentsMargins(0, 0, 0, 0)
        editing_layout.setSpacing(0)
        editing_layout.addStretch(1)
        self.content_widget.setMaximumWidth(960)
        editing_layout.addWidget(self.content_widget, 10)
        editing_layout.addStretch(1)
        layout.addWidget(editing_area, 1)
        self.setCentralWidget(root)
        self.content_widget.layout().setContentsMargins(20, 14, 20, 10)
        self.content_widget.layout().setSpacing(10)
        self.subtitle.hide()
        # A compact fixed observation strip above one property scroll area.
        while self.body_layout.count():
            self.body_layout.takeAt(0)
        body_widget = QWidget()
        body = QVBoxLayout(body_widget)
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(12)
        body.addWidget(self.preview, 0, Qt.AlignmentFlag.AlignHCenter)
        body.addWidget(self.stack, 1)
        self.body_layout.addWidget(body_widget)
        self.preview.setObjectName('referencePreview')
        self.preview.setMinimumWidth(0)
        self.preview.setMaximumWidth(740)
        self.preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.preview.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.preview.setFixedHeight(160)
        self.preview.layout().setContentsMargins(10, 6, 10, 6)
        self.preview.layout().setSpacing(4)
        self.preview.selected_label.hide()
        background_group = self.preview.background_label.parentWidget()
        choices = self.preview.background.choice_buttons[0].parentWidget()
        self._previous_background_layout = QWidget()
        self._previous_background_layout.setLayout(background_group.layout())
        compact_background = QHBoxLayout(background_group)
        compact_background.setContentsMargins(0, 0, 0, 0)
        compact_background.setSpacing(4)
        compact_background.addWidget(self.preview.background_label)
        compact_background.addWidget(choices)
        background_group.setFixedWidth(174)
        scale_group = self.preview.scale.choice_buttons[0].parentWidget()
        scale_group.setFixedWidth(96)
        toolbar = self.preview.layout().itemAt(0).layout()
        for index in range(toolbar.count()):
            toolbar.setStretch(index, 0)
        toolbar.addStretch(1)
        for button in self.preview.role_buttons.values():
            button.hide()
        for surface in self.preview.surfaces:
            surface.setMinimumHeight(84)
        self.preview.scale.setCurrentIndex(1)
        self._appearance_groups()
        self._preference_groups()
        self._reference_ready = True
        self._apply_reference_theme()
        for widget in self.findChildren(QWidget):
            if widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
                widget.setProperty('keyboardFocus', False)
                widget.installEventFilter(self)
        self.select_page(0)
        self.sync()

    def _appearance_groups(self):
        page = self.pages[0]
        old_layout = page.family_layout
        self._previous_appearance = QWidget()
        self._previous_appearance.setLayout(old_layout)
        self._previous_appearance.hide()
        form = QVBoxLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        page.family_layout = form
        self.shape_gallery = ShapeGallery(page.shape_buttons.values())
        group(form, '造型', [self.shape_gallery])
        size = segmented_combo(page.family_size, ('24', '32', '40', '48', '64'))
        adaptation = segmented_combo(page.family_appearance, ('自动', '浅色', '深色'))
        history = controls([page.legacy_toggle, page.legacy_style])
        palettes = QWidget()
        grid = QGridLayout(palettes)
        grid.setContentsMargins(8, 6, 8, 6)
        grid.setSpacing(4)
        page.preset_grid = grid
        for index, (button, _) in enumerate(page.preset_buttons):
            button.setMinimumHeight(44)
            button.setFixedHeight(58)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setIconSize(QSize(80, 32))
            grid.addWidget(button, index // 4, index % 4)
        page._preset_columns = 4
        page._reference_palette_columns = 4
        group(form, '配色', [palettes, row('当前配色', controls([page.palette_name, page.reset_palette])), row('自定义', page.palette_button)])
        form.addWidget(page.inline_colors)
        group(form, '属性', [row('尺寸 · px', size), row('背景适配', adaptation), row('历史造型', history)])
        form.addStretch()

    def _preference_groups(self):
        page = self.pages[3]
        theme_import = page.findChild(QPushButton, 'importThemeBtn')
        theme_export = page.findChild(QPushButton, 'exportThemeBtn')
        restore = page.findChild(QPushButton, 'restoreButton')
        old_layout = page.layout()
        self._previous_preferences = QWidget()
        self._previous_preferences.setLayout(old_layout)
        self._previous_preferences.hide()
        form = QVBoxLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(8)
        self.theme_selector = ThemeSelector(self)
        group(form, '界面', [row('窗口主题', self.theme_selector)])
        group(form, '后台 · 立即生效', [row('登录时启动', page.startup), row('光标服务', controls([page.pause_btn, page.resume_btn]))])
        group(form, '偏好 · 应用后生效', [row('摇动寻标', page.shake_switch), row('全屏免打扰', page.game_switch), row('托盘入口', page.tray_switch), row('自动检查更新', page.auto_update_switch)])
        page.update_status_lbl.setWordWrap(True)
        page.update_status_lbl.setObjectName('referenceNote')
        group(form, '版本', [row('Pointer', QLabel(self.current_version())), row('检查更新', page.check_update_btn), page.update_status_lbl])
        imports = QPushButton('导入 JSON')
        imports.clicked.connect(self.import_settings)
        exports = QPushButton('导出 JSON')
        exports.clicked.connect(self.export_settings)
        reset = QPushButton('重置默认参数')
        reset.setAccessibleName('重置光标默认参数，加入草稿')
        reset.setToolTip('恢复默认造型、配色和动效；点击应用后生效。保留启动、托盘和更新偏好。')
        reset.clicked.connect(self.reset_defaults)
        group(form, '配置', [row('主题包', controls([theme_import, theme_export])), row('JSON', controls([imports, exports])), row('默认配置', reset)])
        group(form, '恢复', [row('原光标备份', restore)])
        form.addStretch()

    def _apply_reference_theme(self):
        from .theme import STYLE
        from .family_workspace import workspace_style
        self.confirmation_colors = reference_colors(self.ui_dark)
        self.setStyleSheet(STYLE + workspace_style(self.ui_dark) + reference_style(self.ui_dark))
        for index, button in enumerate(self.navigation):
            icon = navigation_icon(index, self.ui_dark, self.devicePixelRatioF())
            white = navigation_icon(index, False, self.devicePixelRatioF())
            icon.addPixmap(white.pixmap(QSize(18, 18), QIcon.Mode.Normal, QIcon.State.On), QIcon.Mode.Normal, QIcon.State.On)
            button.setIcon(icon)

    def toggle_workspace_theme(self):
        super().toggle_workspace_theme()
        if self._reference_ready:
            self._apply_reference_theme()
            self.theme_selector.sync()

    def select_page(self, index):
        super().select_page(index)
        if self._reference_ready:
            self.stack.setMinimumWidth(0)
            self.stack.setMaximumWidth(16777215)
            self.preview.setVisible(index in (0, 1))
            self.subtitle.hide()

    def sync(self):
        super().sync()
        if self._reference_ready:
            self.theme_selector.sync()
            self._fit_reference_width()
            from pointer.cursor.resources import canvas_size
            height = canvas_size(self._draft) + 24
            for surface in self.preview.surfaces:
                surface.setMinimumHeight(height)
            self.preview.setFixedHeight(max(160, height + 76))

    def _fit_reference_width(self):
        self.content_widget.setFixedWidth(min(960, max(0, self.width() - 190)))
        self.preview.setFixedWidth(min(740, max(0, self.content_widget.width() - 40)))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._reference_ready:
            self.nav_rail.setFixedWidth(190)
            self._fit_reference_width()
