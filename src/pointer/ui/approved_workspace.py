"""Two-page implementation of the approved graphite direction, review only.

Reuse models, cursor pixels and callbacks; isolate visual changes from the
rejected reference shell and the production launch path.
"""
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QVBoxLayout, QHBoxLayout, QGridLayout, QToolButton
from .reference_workspace import ReferenceWindow, ShapeGallery, row, controls
from .family_workspace import navigation_icon, segmented_combo, workspace_style
from .theme import STYLE, HairlineDivider
from .colors import theme_colors


def approved_colors(dark):
    colors = dict(theme_colors(dark))
    colors.update(canvas='#25272b' if dark else '#f1f2f5',
                  surface='#2e3136' if dark else '#fafbfd',
                  raised='#383d45' if dark else '#e6eaf0',
                  text='#eef0f4' if dark else '#242831',
                  muted='#aeb4bf' if dark else '#5b6370',
                  border='#41464f' if dark else '#cfd5df',
                  divider='#3b4048' if dark else '#dde1e8',
                  selected='#2765bf', selected_text='#ffffff',
                  shape_selected_border='#528dde' if dark else '#2765bf',
                  focus='#8dbcff' if dark else '#1760bc',
                  on_track='#2765bf', on_border='#7198ce' if dark else '#2765bf')
    return colors


def approved_style(dark):
    c = approved_colors(dark)
    sidebar = '#242a34' if dark else '#e3e8f0'
    selected_fill = '#343f51' if dark else '#e1ebfa'
    return f'''
        #referenceShell, #content, #approvedEditingArea {{ background: {c['canvas']}; }}
        #referenceSidebar, #navCapsule {{ background: {sidebar}; border-radius: 0; }}
        #referenceSidebar {{ border-right: 1px solid {c['border']}; }}
        #referenceBrand {{ color: {c['text']}; font-size: 17px; font-weight: 600; }}
        #navCapsule QPushButton {{ border: none; border-radius: 6px; min-height: 28px;
            max-height: 28px; padding: 5px 12px; font-size: 14px; text-align: left;
            background: transparent; color: {c['text']}; }}
        #navCapsule QPushButton:hover {{ background: {c['raised']}; }}
        #navCapsule QPushButton:checked {{ background: {c['selected']}; color: white; }}
        #pageTitle {{ color: {c['text']}; font-size: 16px; font-weight: 600; }}
        #approvedHeading {{ color: {c['muted']}; font-size: 13px; font-weight: 500; }}
        #approvedPaletteStatus {{ color: {c['muted']}; font-size: 12px; }}
        #approvedGroup, #referenceGroup, #referencePreview {{ background: {c['surface']};
            border: 1px solid {c['border']}; border-radius: 9px; }}
        #approvedHeadingRow, #approvedGallery {{ background: transparent; border: none; }}
        #referenceRow {{ background: transparent; border: none; min-height: 36px; }}
        #referenceRow QLabel {{ color: {c['text']}; background: transparent; font-size: 13px; }}
        #referenceSection {{ color: {c['muted']}; font-size: 13px; font-weight: 500; }}
        #hairlineDivider {{ background: {c['divider']}; border: none; }}
        QToolButton#approvedShape, QToolButton#paletteSpecimen {{ color: {c['text']};
            background: transparent; border: 1px solid transparent; border-radius: 6px;
            padding: 4px; font-size: 13px; }}
        QToolButton#approvedShape:hover, QToolButton#paletteSpecimen:hover {{ background: {c['raised']}; }}
        QToolButton#approvedShape:checked {{
            background: {selected_fill}; border: 1px solid {c['shape_selected_border']}; }}
        QToolButton#paletteSpecimen:checked {{
            background: {selected_fill}; border: 1px solid {c['selected']}; }}
        QToolButton[segmented="true"] {{ background: transparent; border: 1px solid transparent;
            border-radius: 5px; padding: 3px 5px; min-height: 24px; font-size: 13px; }}
        QToolButton[segmented="true"]:checked {{ background: {c['raised']}; border-color: {c['border']}; color: {c['text']}; }}
        QToolButton[segmented="true"]:hover {{ background: {c['raised']}; }}
        QPushButton {{ color: {c['text']}; background: {c['raised']}; border: 1px solid transparent;
            border-radius: 5px; padding: 4px 10px; min-height: 22px; font-size: 13px; }}
        QPushButton:hover {{ border-color: {c['border']}; }}
        #compactAction, #legacyToggle {{ background: transparent; color: {c['muted']}; font-size: 12px; }}
        #applyButton {{ background: {c['selected']}; color: white; border-radius: 6px; }}
        #applyButton:disabled {{ color: {c['muted']}; background: {c['raised']}; }}
        #controlBar {{ background: {c['canvas']}; border: none; border-top: 1px solid {c['divider']}; border-radius: 0; }}
        #muted, #feedback, #referenceNote {{ color: {c['muted']}; font-size: 12px; }}
        QComboBox, QLineEdit {{ background: {c['surface']}; color: {c['text']}; border: 1px solid {c['border']};
            border-radius: 5px; padding: 4px 10px; min-height: 22px; font-size: 13px; }}
        QComboBox {{ padding-right: 22px; }}
        QComboBox QAbstractItemView {{ background: {c['surface']}; color: {c['text']};
            selection-background-color: {c['selected']}; selection-color: white; }}
        QToolButton[keyboardFocus="true"]:focus, QPushButton[keyboardFocus="true"]:focus,
        QComboBox[keyboardFocus="true"]:focus, QLineEdit[keyboardFocus="true"]:focus {{ border: 2px solid {c['focus']}; }}
    '''


def panel(layout, title, widgets, status=None):
    if title:
        heading = QWidget()
        heading.setObjectName('approvedHeadingRow')
        line = QHBoxLayout(heading)
        line.setContentsMargins(0, 0, 0, 0)
        label = QLabel(title)
        label.setObjectName('approvedHeading')
        line.addWidget(label, 1)
        if status:
            status.setObjectName('approvedPaletteStatus')
            line.addWidget(status)
        layout.addWidget(heading)
    frame = QFrame()
    frame.setObjectName('approvedGroup')
    inner = QVBoxLayout(frame)
    inner.setContentsMargins(0, 0, 0, 0)
    inner.setSpacing(0)
    for index, widget in enumerate(widgets):
        if index:
            inner.addWidget(HairlineDivider())
        inner.addWidget(widget)
    layout.addWidget(frame)
    return frame


class ApprovedWindow(ReferenceWindow):
    def __init__(self, application):
        super().__init__(application)
        self.content_widget.layout().setContentsMargins(24, 14, 24, 12)
        self.content_widget.layout().setSpacing(10)
        bar = self.findChild(QFrame, 'controlBar')
        bar.setFixedHeight(52)
        bar.layout().setContentsMargins(12, 8, 12, 8)
        self.content_widget.parentWidget().setObjectName('approvedEditingArea')
        self.preview.setMaximumWidth(16777215)
        self.preview.layout().setContentsMargins(12, 8, 12, 8)
        for combo in (self.preview.background, self.preview.scale, self.pages[0].family_size, self.pages[0].family_appearance):
            for button in combo.choice_buttons:
                button.setMinimumHeight(30)
        self.preview.role.setFixedWidth(104)
        self.preview.role.setFixedHeight(34)
        self.resize(1100, 830)
        if not self.ui_dark:
            self.toggle_workspace_theme()
        self.sync()

    def _appearance_groups(self):
        page = self.pages[0]
        self._previous_appearance = QWidget()
        self._previous_appearance.setLayout(page.family_layout)
        self._previous_appearance.hide()
        form = QVBoxLayout(page)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(9)
        page.family_layout = form
        self.shape_gallery = ShapeGallery(page.shape_buttons.values())
        self.shape_gallery.setObjectName('approvedGallery')
        self.shape_gallery.grid.setContentsMargins(12, 10, 12, 10)
        for button in page.shape_buttons.values():
            button.setObjectName('approvedShape')
        panel(form, '造型', [self.shape_gallery])
        gallery = QWidget()
        gallery.setObjectName('approvedGallery')
        grid = QGridLayout(gallery)
        grid.setContentsMargins(12, 10, 12, 10)
        grid.setSpacing(6)
        page.preset_grid = grid
        for index, (button, _) in enumerate(page.preset_buttons):
            button.setFixedHeight(60)
            button.setIconSize(QSize(80, 32))
            grid.addWidget(button, index // 4, index % 4)
        page._preset_columns = page._reference_palette_columns = 4
        panel(form, '配色', [gallery], page.palette_name)
        size = segmented_combo(page.family_size, ('24', '32', '40', '48', '64'))
        adaptation = segmented_combo(page.family_appearance, ('自动', '浅色', '深色'))
        page.palette_button.setText('编辑配色…')
        page.reset_palette.setText('重置')
        custom = controls([page.reset_palette, page.palette_button, page.legacy_toggle])
        panel(form, None, [row('尺寸 · px', size), row('背景适配', adaptation), row('自定义', custom)])
        form.addWidget(page.inline_colors)
        self.history_row = row('历史造型', page.legacy_style)
        self.history_row.hide()
        page.legacy_toggle.toggled.connect(self.history_row.setVisible)
        form.addWidget(self.history_row)
        form.addStretch(1)

    def _apply_reference_theme(self):
        self.confirmation_colors = approved_colors(self.ui_dark)
        self.setStyleSheet(STYLE + workspace_style(self.ui_dark) + approved_style(self.ui_dark))
        for index, button in enumerate(self.navigation):
            icon = navigation_icon(index, self.ui_dark, self.devicePixelRatioF())
            white = navigation_icon(index, False, self.devicePixelRatioF())
            icon.addPixmap(white.pixmap(QSize(18, 18), QIcon.Mode.Normal, QIcon.State.On), QIcon.Mode.Normal, QIcon.State.On)
            button.setIcon(icon)

    def _preference_groups(self):
        super()._preference_groups()
        note = self.pages[3].update_status_lbl
        note.setContentsMargins(12, 4, 12, 6)
        note.setMinimumHeight(28)

    def _fit_reference_width(self):
        self.content_widget.setFixedWidth(min(960, max(0, self.width() - 190)))
        # All content groups have the same left and right edge.
        self.preview.setFixedWidth(max(0, self.content_widget.width() - 48))

    def sync(self):
        super().sync()
        if self._reference_ready:
            from pointer.cursor.resources import canvas_size
            height = max(98, canvas_size(self._draft) + 24)
            for surface in self.preview.surfaces:
                surface.setMinimumHeight(height)
            self.preview.setFixedHeight(height + 78)
