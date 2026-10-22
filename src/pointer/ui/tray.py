"""System tray controls that explicitly edit the workspace draft."""
from PySide6.QtCore import QObject
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from pointer.paths import ROOT, INSTALL_ROOT
from .colors import theme_colors


class TrayController(QObject):
    """Own one tray icon and keep its menu in sync without recreating actions."""
    def __init__(self, main_window):
        super().__init__(main_window)
        self.window = main_window
        self.tray = None
        self.menu = None
        self._choices = []
        self._toggles = []
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon_path = next((path for path in (
            ROOT / 'pointer.ico', ROOT / 'packaging' / 'windows' / 'pointer.ico',
            INSTALL_ROOT / 'pointer.ico',
        ) if path.exists()), None)
        icon = QIcon(str(icon_path)) if icon_path else QIcon()
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip('Pointer · 光标工作台')
        self.tray.activated.connect(self._on_activated)
        self._build_menu()
        self.update_menu()
        self.tray.show()

    def _build_menu(self):
        previous = self.menu
        menu = self.menu = QMenu(self.window)
        self._choices = []
        self._toggles = []
        title = menu.addAction('Pointer Studio')
        title.setEnabled(False)
        self.draft_status = menu.addAction('')
        self.draft_status.setEnabled(False)
        menu.addSeparator()
        menu.addAction('显示工作台', self._show_window)
        menu.addSeparator()

        groups = (
            ('外观方案 · 草稿', 'appearance', (
                ('自适应背景', 'adaptive'), ('固定浅色方案', 'light'), ('固定深色方案', 'dark'))),
            ('光标形态 · 草稿', 'style', (
                ('经典圆角 (Sequoia Smooth)', 'sequoia'), ('精准十字 (Precision Studio)', 'precision'),
                ('机甲科技 (Cyber Falcon)', 'falcon'), ('复古像素 (Pixel HD)', 'pixel'))),
            ('触感动效 · 草稿', 'motion', (
                ('整体倾侧 (Tilt)', 'tilt'), ('缩小回弹 (Shrink)', 'shrink'),
                ('弹簧果冻 (Spring)', 'spring'), ('关闭动效 (Off)', 'off'))),
        )
        for title, field, values in groups:
            submenu = menu.addMenu(title)
            for text, value in values:
                action = submenu.addAction(text)
                action.setData(value)
                action.setCheckable(True)
                action.triggered.connect(lambda checked=False, f=field, v=value: self._edit_draft(**{f: v}))
                self._choices.append((action, field, value))
            if field == 'motion':
                self.retired_motion = submenu.addAction('叠加动效已停用（配置保留）')
                self.retired_motion.setData('retired_overlay')
                self.retired_motion.setCheckable(True)
                self.retired_motion.setChecked(True)
                self.retired_motion.setEnabled(False)

        menu.addSeparator()
        for text, field in (('晃动放大寻针 · 草稿', 'shake_to_find'), ('游戏全屏免打扰 · 草稿', 'game_dnd')):
            action = menu.addAction(text)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, f=field: self._edit_draft(**{f: checked}))
            self._toggles.append((action, field))
        self.apply_action = menu.addAction('应用草稿', self._apply_draft)
        menu.addSeparator()
        self.update_action = menu.addAction('检查更新…', self._trigger_update_check)
        menu.addSeparator()
        menu.addAction('关闭工作台（后台继续运行）', self._quit_application)
        menu.aboutToShow.connect(self.update_menu)
        self.tray.setContextMenu(menu)
        if previous is not None:
            previous.deleteLater()

    def _edit_draft(self, **fields):
        if getattr(self.window, 'busy', False):
            return
        self.window.change(**fields)
        self.update_menu()

    def _apply_draft(self):
        if getattr(self.window, 'busy', False):
            return
        self._show_window()
        self.window.apply_draft()

    def _show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def _trigger_update_check(self):
        self._show_window()
        if hasattr(self.window, 'check_updates_interactive'):
            self.window.check_updates_interactive()

    def _quit_application(self):
        if not self.window.close():
            return
        from PySide6.QtWidgets import QApplication
        self.dispose()
        app = QApplication.instance()
        if app:
            app.quit()

    def _on_activated(self, reason):
        if reason in (QSystemTrayIcon.ActivationReason.Trigger, QSystemTrayIcon.ActivationReason.DoubleClick):
            if self.window.isVisible() and not self.window.isMinimized():
                self.window.hide()
            else:
                self._show_window()

    def update_menu(self):
        if self.tray is None:
            return
        if self.menu is None:
            self._build_menu()
        draft = self.window.draft()
        dirty = draft != getattr(self.window, 'applied', draft)
        busy = bool(getattr(self.window, 'busy', False))
        self.draft_status.setText('处理中 · 暂不可修改草稿' if busy else
                                  '勾选为未应用草稿 · 应用后生效' if dirty else '勾选为已保存配置 · 修改后需应用')
        for action, field, value in self._choices:
            action.setChecked(getattr(draft, field) == value)
            action.setEnabled(not busy)
        for action, field in self._toggles:
            action.setChecked(getattr(draft, field))
            action.setEnabled(not busy)
        self.retired_motion.setVisible(draft.motion in ('pulse', 'trail'))
        self.apply_action.setEnabled(dirty and not busy and hasattr(self.window, 'apply_draft'))
        self.update_action.setEnabled(not busy)
        colors = getattr(self.window, 'confirmation_colors', theme_colors(bool(getattr(self.window, 'ui_dark', False))))
        self.menu.setStyleSheet(f"""
            QMenu {{ background: {colors['surface']}; color: {colors['text']};
                border: 1px solid {colors['border']}; border-radius: 8px; padding: 4px; font-size: 12px; }}
            QMenu::item {{ padding: 6px 18px 6px 24px; border-radius: 4px; }}
            QMenu::item:selected {{ background: {colors['selected']}; color: {colors['selected_text']}; }}
            QMenu::item:disabled {{ color: {colors['muted']}; }}
            QMenu::separator {{ height: 1px; background: {colors['divider']}; margin: 4px 8px; }}
        """)

    def dispose(self):
        """Release both Qt owners; repeated disable/re-enable never leaves an icon."""
        if self.tray is not None:
            self.tray.hide()
            self.tray.setContextMenu(None)
            self.tray.deleteLater()
            self.tray = None
        if self.menu is not None:
            self.menu.deleteLater()
            self.menu = None
        self.deleteLater()
