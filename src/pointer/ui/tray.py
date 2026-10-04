"""Windows System Tray Mini Island Controller for Pointer."""
from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from pointer.paths import ROOT, INSTALL_ROOT


class TrayController(QObject):
    """System tray mini island providing quick controls, mode toggles, and status."""
    def __init__(self, main_window):
        super().__init__(main_window)
        self.window = main_window
        self.tray = None

        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon_path = None
        for candidate in (
            ROOT / 'pointer.ico',
            ROOT / 'packaging' / 'windows' / 'pointer.ico',
            INSTALL_ROOT / 'pointer.ico',
        ):
            if candidate.exists():
                icon_path = candidate
                break
        icon = QIcon(str(icon_path)) if icon_path else QIcon()

        self.tray = QSystemTrayIcon(icon, main_window)
        self.tray.setToolTip("Pointer · 自适应光标工作台")
        self.tray.activated.connect(self._on_activated)

        self._build_menu()
        self.tray.show()

    def _build_menu(self):
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #242427;
                color: #f5f5f7;
                border: 0.5px solid rgba(255, 255, 255, 0.15);
                border-radius: 8px;
                padding: 4px;
                font-size: 12px;
            }
            QMenu::item {
                padding: 6px 18px 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #007aff;
                color: #ffffff;
            }
            QMenu::separator {
                height: 1px;
                background-color: rgba(255, 255, 255, 0.1);
                margin: 4px 8px;
            }
        """)

        # Title
        title_action = menu.addAction("Pointer Studio")
        title_action.setEnabled(False)

        menu.addSeparator()

        show_action = menu.addAction("显示工作台")
        show_action.triggered.connect(self._show_window)

        menu.addSeparator()

        # Appearance submenu
        app_menu = menu.addMenu("🎨 外观方案")
        for text, mode in [
            ("自适应背景", "adaptive"),
            ("固定浅色方案", "light"),
            ("固定深色方案", "dark"),
        ]:
            act = app_menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(self.window.draft().appearance == mode)
            act.triggered.connect(lambda checked=False, m=mode: self.window.change(appearance=m))

        # Geometric Style submenu
        style_menu = menu.addMenu("📐 光标形态")
        for text, st in [
            ("经典圆角 (Sequoia Smooth)", "sequoia"),
            ("精准十字 (Precision Studio)", "precision"),
            ("机甲科技 (Cyber Falcon)", "falcon"),
            ("复古像素 (Pixel HD)", "pixel"),
        ]:
            act = style_menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(self.window.draft().style == st)
            act.triggered.connect(lambda checked=False, s=st: self.window.change(style=s))

        # Motion submenu
        motion_menu = menu.addMenu("⚡ 触感动效")
        for text, mo in [
            ("整体倾侧 (Tilt)", "tilt"),
            ("缩小回弹 (Shrink)", "shrink"),
            ("弹簧果冻 (Spring)", "spring"),
            ("点击冲击波 (Pulse)", "pulse"),
            ("灵动微拖尾 (Trail)", "trail"),
            ("关闭动效 (Off)", "off"),
        ]:
            act = motion_menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(self.window.draft().motion == mo)
            act.triggered.connect(lambda checked=False, m=mo: self.window.change(motion=m))

        menu.addSeparator()

        # Innovations
        shake_act = menu.addAction("晃动放大寻针 (Shake-to-Find)")
        shake_act.setCheckable(True)
        shake_act.setChecked(self.window.draft().shake_to_find)
        shake_act.triggered.connect(lambda checked: self.window.change(shake_to_find=checked))

        game_act = menu.addAction("游戏全屏免打扰")
        game_act.setCheckable(True)
        game_act.setChecked(self.window.draft().game_dnd)
        game_act.triggered.connect(lambda checked: self.window.change(game_dnd=checked))

        menu.addSeparator()

        update_act = menu.addAction("🔄 检查更新…")
        update_act.triggered.connect(self._trigger_update_check)

        menu.addSeparator()

        quit_act = menu.addAction("🚪 退出 Pointer")
        quit_act.triggered.connect(self._quit_application)

        self.tray.setContextMenu(menu)

    def _show_window(self):
        self.window.showNormal()
        self.window.raise_()
        self.window.activateWindow()

    def _trigger_update_check(self):
        self._show_window()
        if hasattr(self.window, "check_updates_interactive"):
            self.window.check_updates_interactive()

    def _quit_application(self):
        from PySide6.QtWidgets import QApplication
        self.tray.hide()
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
        self._build_menu()
