"""Approved v2 observation/property workspace; cursor renderer and models reused."""
from dataclasses import replace
from PySide6.QtCore import Qt, QSize, QPointF, QRectF, QEvent
from PySide6.QtGui import QPainter, QColor, QPen, QIcon
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QSizePolicy
from pointer.cursor.resources import canvas_size
from .reference_workspace import ReferenceWindow, row, controls
from .approved_workspace import approved_colors, approved_style, panel
from .family_workspace import FamilySurface, cursor_pixmap, DPI_VARIANTS, navigation_icon, segmented_combo, workspace_style
from .theme import STYLE, HairlineDivider


class ObservationSurface(FamilySurface):
    """Original input handling and exact cached cursor pixels on an uncluttered stage."""
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        theme = self.theme
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor('#eef0f5' if theme == 'light' else '#202329'))
        painter.drawRoundedRect(QRectF(self.rect()), 8, 8)
        painter.setPen(QColor('#616979' if theme == 'light' else '#b0b6c2'))
        painter.drawText(self.rect().adjusted(8, 12, -8, -8), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter,
                         '浅色背景' if theme == 'light' else '深色背景')
        settings = self.owner.settings
        effective = settings.appearance if settings.appearance in ('light', 'dark') else theme
        role = self.owner.role.currentData() or 'arrow'
        frame = self.owner.frame if role in ('arrow', 'hand') else self.owner.loading_frame if role in ('busy', 'working') else 0
        rendered = settings if self.actual else replace(settings, size=64)
        dpi = min(DPI_VARIANTS, key=lambda value: abs(value-96*self.devicePixelRatioF())) if self.actual else 384
        key = (rendered, role, effective, frame, self.actual, dpi)
        pixmap = self.owner.get_cached_pixmap(key)
        if pixmap is None:
            pixmap = cursor_pixmap(rendered, role, effective, frame, crop=not self.actual, dpi=dpi)
            if self.actual:
                pixmap.setDevicePixelRatio(dpi/96)
            self.owner.put_cached_pixmap(key, pixmap)
        if self.actual:
            size = pixmap.deviceIndependentSize()
        else:
            target = max(24, min(140, self.width()-24, self.height()-56))
            pixmap = pixmap.scaled(target, target, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            size = pixmap.size()
        x, y = (self.width()-size.width())/2, (self.height()-size.height())/2+12
        painter.drawPixmap(QPointF(x, y), pixmap)
        self.cursor_bounds = QRectF(x, y, size.width(), size.height())
        self.last_cursor_key = key
        if (self.hasFocus() and self.property('keyboardFocus')) or self.pressed or self.hovered:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(approved_colors(self.window().ui_dark)['focus']), 2))
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(2, 2, -2, -2), 8, 8)
        painter.end()


class PressTrial(QPushButton):
    def __init__(self, preview):
        super().__init__('按住试验')
        self.preview = preview
        self.setAccessibleName('按住试验当前草稿动效，不应用系统光标')
        self.pressed.connect(lambda: preview.set_down(True))
        self.released.connect(preview.clear_press)

    def event(self, event):
        if event.type() in (QEvent.Type.FocusOut, QEvent.Type.Hide, QEvent.Type.WindowDeactivate, QEvent.Type.UngrabMouse, QEvent.Type.Leave):
            self.preview.clear_press()
        return super().event(event)


class DualWindow(ReferenceWindow):
    def __init__(self, application):
        self._dual_ready = False
        super().__init__(application)
        self.content_widget.layout().setContentsMargins(24, 14, 24, 12)
        self._dual_previous_body = self.body_layout.takeAt(0).widget()
        self._dual_previous_body.hide()
        body = QWidget()
        layout = QHBoxLayout(body)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)
        self._build_observation()
        layout.addWidget(self.preview, 46)
        divider = QFrame()
        divider.setObjectName('dualDivider')
        divider.setFixedWidth(1)
        self.dual_divider = divider
        layout.addWidget(divider)
        layout.addWidget(self.stack, 54)
        self.body_layout.addWidget(body)
        bar = self.findChild(QFrame, 'controlBar')
        bar.setFixedHeight(52)
        bar.layout().setContentsMargins(12, 8, 12, 8)
        self.page_summary = QLabel()
        self.page_summary.setObjectName('dualSummary')
        self.page_summary.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.title.parentWidget().layout().addWidget(self.page_summary)
        self._dual_ready = True
        if not self.ui_dark:
            self.toggle_workspace_theme()
        self.resize(1180, 880)
        self.select_page(0)
        self.sync()
        for widget in self.findChildren(QWidget):
            if widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
                widget.setProperty('keyboardFocus', False)
                widget.installEventFilter(self)

    def _build_observation(self):
        preview = self.preview
        old = QWidget()
        old.setLayout(preview.layout())
        old.hide()
        self._dual_previous_preview = old
        form = QVBoxLayout(preview)
        form.setContentsMargins(12, 12, 12, 12)
        form.setSpacing(8)
        heading = QLabel('光标预览')
        heading.setObjectName('dualHeading')
        modes = preview.scale.choice_buttons[0].parentWidget()
        modes.setFixedWidth(114)
        for button in preview.scale.choice_buttons:
            button.setMinimumHeight(30)
        form.addWidget(controls([heading, modes]))
        for surface in preview.surfaces:
            surface.hide()
        preview.surfaces = [ObservationSurface(preview, theme, actual=True) for theme in ('light', 'dark')]
        preview.hero = preview.actual = preview.surfaces[0]
        stages = QHBoxLayout()
        stages.setSpacing(8)
        for surface in preview.surfaces:
            stages.addWidget(surface, 1)
        form.addLayout(stages)
        form.addWidget(HairlineDivider())
        roles_heading = QLabel('光标角色')
        roles_heading.setObjectName('dualHeading')
        form.addWidget(roles_heading)
        common = QHBoxLayout()
        common.setSpacing(4)
        for button in preview.role_buttons.values():
            button.show()
            button.setMinimumWidth(36)
            button.setFixedHeight(54)
            button.setIconSize(QSize(30, 28))
            common.addWidget(button, 1)
        form.addLayout(common)
        preview.role.setFixedHeight(34)
        preview.role.setMinimumWidth(112)
        preview.role.setMaximumWidth(112)
        form.addWidget(row('全部角色', preview.role))
        form.addWidget(HairlineDivider())
        self.trial_button = PressTrial(preview)
        self.trial_button.setMinimumHeight(34)
        self.trial_button.setFixedWidth(112)
        form.addWidget(controls([QLabel('按住预览或空格'), self.trial_button]))
        preview.actual_label.setWordWrap(True)
        form.addWidget(preview.actual_label)
        form.addStretch(1)
        preview.setMinimumSize(260, 0)
        preview.setMaximumSize(16777215, 16777215)
        preview.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview.background.setCurrentIndex(2)
        preview.scale.setCurrentIndex(1)

    def _appearance_groups(self):
        page = self.pages[0]
        self._previous_appearance = QWidget()
        self._previous_appearance.setLayout(page.family_layout)
        self._previous_appearance.hide()
        form = QVBoxLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        page.family_layout = form
        page.setMinimumSize(0, 0)
        shape_gallery = QWidget()
        shape_gallery.setObjectName('approvedGallery')
        shape_grid = QGridLayout(shape_gallery)
        shape_grid.setContentsMargins(10, 10, 10, 10)
        shape_grid.setSpacing(6)
        for index, button in enumerate(page.shape_buttons.values()):
            button.setObjectName('approvedShape')
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.setMinimumWidth(68)
            button.setFixedHeight(66)
            button.setIconSize(QSize(40, 32))
            shape_grid.addWidget(button, index//3, index%3)
        self.shape_gallery = shape_gallery
        shape_gallery.columns = 3
        panel(form, '造型', [shape_gallery])
        palette_gallery = QWidget()
        palette_gallery.setObjectName('approvedGallery')
        self.palette_gallery = palette_gallery
        palette_gallery.setFixedHeight(146)
        page.preset_grid = QGridLayout(palette_gallery)
        page.preset_grid.setContentsMargins(10, 10, 10, 10)
        page.preset_grid.setSpacing(6)
        for index, (button, _) in enumerate(page.preset_buttons):
            button.setFixedHeight(60)
            button.setIconSize(QSize(80, 32))
            page.preset_grid.addWidget(button, index//4, index%4)
        page._preset_columns = page._reference_palette_columns = 4
        panel(form, '配色', [palette_gallery], page.palette_name)
        size = segmented_combo(page.family_size, ('24', '32', '40', '48', '64'))
        appearance = segmented_combo(page.family_appearance, ('自动', '浅色', '深色'))
        for control in (page.family_size, page.family_appearance):
            for button in control.choice_buttons:
                button.setMinimumHeight(34)
                button.setMinimumWidth(24)
        page.palette_button.setText('编辑配色…')
        page.reset_palette.setText('重置')
        page.legacy_toggle.setText('更多')
        panel(form, None, [row('尺寸 · px', size), row('背景适配', appearance),
                           row('自定义', controls([page.reset_palette, page.palette_button, page.legacy_toggle]))])
        form.addWidget(page.inline_colors)
        self.history_row = row('历史造型', page.legacy_style)
        self.history_row.hide()
        page.legacy_toggle.toggled.connect(self.history_row.setVisible)
        form.addWidget(self.history_row)
        form.addStretch(1)

    def _preference_groups(self):
        super()._preference_groups()
        self.pages[3].update_status_lbl.setContentsMargins(12, 4, 12, 6)
        self.pages[3].update_status_lbl.setMinimumHeight(28)

    def _apply_reference_theme(self):
        c = approved_colors(self.ui_dark)
        self.confirmation_colors = c
        self.setStyleSheet(STYLE + workspace_style(self.ui_dark) + approved_style(self.ui_dark) + f'''
            #dualHeading {{ color: {c['muted']}; font-size: 13px; }}
            #dualSummary {{ color: {c['muted']}; font-size: 13px; }}
            #dualDivider {{ background: {c['divider']}; border: none; }}
            #referencePreview {{ background: transparent; border: none; }}
            QToolButton[segmented="true"] {{ min-width: 20px; padding: 3px; }}
            QToolButton#roleSpecimen {{ background: transparent; border: 1px solid transparent;
                border-radius: 6px; padding: 3px; font-size: 12px; color: {c['text']}; }}
            QToolButton#roleSpecimen:checked {{ background: {c['raised']}; border-color: {c['border']}; }}
            QToolButton#roleSpecimen[keyboardFocus="true"]:focus {{ border: 2px solid {c['focus']}; }}
        ''')
        for index, button in enumerate(self.navigation):
            icon = navigation_icon(index, self.ui_dark, self.devicePixelRatioF())
            white = navigation_icon(index, False, self.devicePixelRatioF())
            icon.addPixmap(white.pixmap(QSize(18, 18), QIcon.Mode.Normal, QIcon.State.On), QIcon.Mode.Normal, QIcon.State.On)
            button.setIcon(icon)

    def _fit_reference_width(self):
        self.content_widget.setFixedWidth(min(1100, max(0, self.width()-190)))

    def select_page(self, index):
        super().select_page(index)
        if self._dual_ready:
            self.preview.setVisible(index in (0, 1))
            self.dual_divider.setVisible(index in (0, 1))
            self.page_summary.setVisible(index == 0)

    def sync(self):
        # ReferenceWindow's preview-height adjustment belongs to its vertical
        # shell; use the original model sync and only this shell's geometry.
        from .main_window import MainWindow
        MainWindow.sync(self)
        if self._dual_ready:
            self._fit_reference_width()
            height = max(200, canvas_size(self._draft)+54)
            for surface in self.preview.surfaces:
                surface.setMinimumHeight(height)
                surface.setMaximumHeight(height)
            self.page_summary.setText(self.pages[0].shape_buttons.get(self._draft.style).text() + ' · ' + self.pages[0].palette_name.text()
                                      if self._draft.style in self.pages[0].shape_buttons else '历史造型 · '+self.pages[0].palette_name.text())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._dual_ready:
            page = self.pages[0]
            columns = 4 if self.width() >= 1000 else 2
            self.palette_gallery.setFixedHeight(146 if columns == 4 else 278)
            if page._preset_columns != columns:
                page._reference_palette_columns = page._preset_columns = columns
                for index, (button, _) in enumerate(page.preset_buttons):
                    page.preset_grid.removeWidget(button)
                    page.preset_grid.addWidget(button, index//columns, index%columns)
                page.preset_grid.invalidate()
                page.updateGeometry()
