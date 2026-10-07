from math import cos, sin, pi
from PySide6.QtCore import Qt, QEvent, QSize, QPointF
from PySide6.QtGui import QIcon, QPixmap, QPainter, QPainterPath, QColor, QPen
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QGridLayout, QLabel, QFrame, QButtonGroup
)
from ..theme import card, SettingsRow, HairlineDivider, MacSwitch
from ..colors import widget_colors


def theme_choice_icon(dark, color, dpr):
    pixmap = QPixmap(round(16 * dpr), round(16 * dpr))
    pixmap.setDevicePixelRatio(dpr)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    pen = QPen(QColor(color), 1.4)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    if dark:
        moon = QPainterPath(QPointF(11.7, 1.8))
        moon.cubicTo(9.7, 4.7, 11.0, 8.2, 14.0, 8.8)
        moon.cubicTo(13.6, 12.4, 10.2, 14.7, 6.8, 13.7)
        moon.cubicTo(3.4, 12.8, 1.5, 9.2, 2.7, 5.8)
        moon.cubicTo(4.0, 2.6, 8.4, 0.9, 11.7, 1.8)
        moon.closeSubpath()
        painter.drawPath(moon)
    else:
        painter.drawEllipse(QPointF(8, 8), 2.7, 2.7)
        for ray in range(8):
            angle = ray * pi / 4
            painter.drawLine(QPointF(8 + cos(angle) * 5.5, 8 + sin(angle) * 5.5),
                             QPointF(8 + cos(angle) * 7, 8 + sin(angle) * 7))
    painter.end()
    return QIcon(pixmap)


class ThemeSelector(QWidget):
    """Choose a window appearance without changing either configuration draft."""
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setObjectName('themeSelector')
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setAccessibleName('窗口主题')
        self.setFixedSize(168, 34)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 3, 3, 3)
        layout.setSpacing(2)
        self.buttons = {False: QPushButton('浅色'), True: owner.theme_button}
        self._style_colors = None
        self.buttons[True].clicked.disconnect(owner.toggle_workspace_theme)
        self.button_group = QButtonGroup(self)
        for dark, button in self.buttons.items():
            button.setFixedHeight(28)
            button.setCheckable(True)
            button.setAutoDefault(False)
            button.setIconSize(QSize(16, 16))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip('仅更改窗口外观，不修改光标配置')
            button.clicked.connect(lambda checked=False, dark=dark: self.choose(dark))
            button.installEventFilter(self)
            self.button_group.addButton(button, int(dark))
            layout.addWidget(button, 1)
        self.sync()

    def choose(self, dark):
        if bool(dark) != self.owner.ui_dark:
            self.owner.toggle_workspace_theme()
        self.sync()

    def sync(self):
        c = widget_colors(self)
        for dark, button in self.buttons.items():
            checked = dark == self.owner.ui_dark
            blocked = button.blockSignals(True)
            button.setChecked(checked)
            button.blockSignals(blocked)
            title = '深色' if dark else '浅色'
            button.setText(title)
            button.setAccessibleName(title + ('窗口主题，当前已选中' if checked else '窗口主题'))
            button.setFocusPolicy(Qt.FocusPolicy.StrongFocus if checked else Qt.FocusPolicy.ClickFocus)
            button.setIcon(theme_choice_icon(dark, c['text'] if checked else c['muted'],
                                             self.owner.devicePixelRatioF()))
        if self._style_colors == c:
            return
        self._style_colors = dict(c)
        self.setStyleSheet(f'''
            #themeSelector {{ background: {c['raised']}; border: 1px solid {c['border']}; border-radius: 8px; }}
            #themeSelector QPushButton {{ color: {c['muted']}; background: transparent;
                border: 1px solid transparent; border-radius: 5px; padding: 0 8px;
                min-height: 0; font-size: 13px; }}
            #themeSelector QPushButton:hover {{ color: {c['text']}; background: {c['canvas']}; }}
            #themeSelector QPushButton:checked {{ color: {c['text']}; background: {c['surface']};
                border-color: {c['border']}; font-weight: 600; }}
            #themeSelector QPushButton:pressed {{ background: {c['canvas']}; }}
            #themeSelector QPushButton[keyboardFocus="true"]:focus {{ border-color: {c['focus']}; }}
            #themeSelector QPushButton:disabled {{ color: {c['disabled_text']}; }}
        ''')

    def eventFilter(self, watched, event):
        if (event.type() == QEvent.Type.KeyPress
                and event.modifiers() in (Qt.KeyboardModifier.NoModifier, Qt.KeyboardModifier.KeypadModifier)):
            if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Home, Qt.Key.Key_Right, Qt.Key.Key_End):
                dark = event.key() in (Qt.Key.Key_Right, Qt.Key.Key_End)
                self.buttons[dark].setFocus(Qt.FocusReason.ShortcutFocusReason)
                self.choose(dark)
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.choose(watched is self.buttons[True])
                return True
        return super().eventFilter(watched, event)


class PreferencesPage(QWidget):
    """System & Preferences: Startup self-healing, profile backups, and background service."""
    def __init__(self, owner):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        frame_ui, inner_ui = card('界面与关于')
        inner_ui.addWidget(SettingsRow('界面主题', widget=owner.theme_button))
        version = QLabel('Pointer ' + owner.current_version())
        version.setObjectName('muted')
        inner_ui.addWidget(version)
        layout.addWidget(frame_ui)

        # 1. Service Runtime & Startup
        frame, inner = card('后台运行与启动', '启动设置与暂停、恢复操作立即生效。')

        # Row 1: Startup switch
        self.startup = MacSwitch()
        self.startup.setObjectName('startupCheck')
        self.startup.toggled.connect(
            lambda enabled: owner.run_operation(lambda: owner.application.set_startup(enabled), '开机启动设置已更新')
        )
        row1 = SettingsRow('登录 Windows 时启动', '在登录后启动 Pointer 后台服务。', self.startup)
        inner.addWidget(row1)

        inner.addWidget(HairlineDivider())

        # Row 2: Pause / Resume buttons
        btn_box = QWidget()
        btn_layout = QHBoxLayout(btn_box)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(8)

        self.pause_btn = QPushButton('暂停光标效果')
        self.pause_btn.setObjectName('pauseButton')
        self.pause_btn.clicked.connect(
            lambda checked=False: owner.run_operation(owner.application.pause, '运行状态已更新')
        )
        btn_layout.addWidget(self.pause_btn)

        self.resume_btn = QPushButton('恢复光标运行')
        self.resume_btn.setObjectName('resumeButton')
        self.resume_btn.clicked.connect(
            lambda checked=False: owner.run_operation(owner.application.resume, '运行状态已更新')
        )
        btn_layout.addWidget(self.resume_btn)

        row2 = SettingsRow('后台运行', '暂停或恢复光标效果。', btn_box)
        inner.addWidget(row2)
        layout.addWidget(frame)

        # 2. Smart Enhancements & Focus Experience
        frame_smart, inner_smart = card('使用体验', '以下修改加入草稿，点击顶部「应用更改」生效。')

        self.shake_switch = MacSwitch()
        self.shake_switch.setObjectName('shakeCheck')
        self.shake_switch.toggled.connect(lambda enabled: owner.change(shake_to_find=enabled))
        row_shake = SettingsRow('晃动鼠标寻找指针', '快速晃动时放大指针，停止后恢复。', self.shake_switch)
        inner_smart.addWidget(row_shake)

        inner_smart.addWidget(HairlineDivider())

        self.game_switch = MacSwitch()
        self.game_switch.setObjectName('gameCheck')
        self.game_switch.toggled.connect(lambda enabled: owner.change(game_dnd=enabled))
        row_game = SettingsRow('全屏免打扰', '全屏应用中暂停自适应效果。', self.game_switch)
        inner_smart.addWidget(row_game)

        inner_smart.addWidget(HairlineDivider())

        self.tray_switch = MacSwitch()
        self.tray_switch.setObjectName('trayCheck')
        self.tray_switch.toggled.connect(lambda enabled: owner.change(tray_enabled=enabled))
        row_tray = SettingsRow('系统托盘', '在任务栏托盘提供后台控制入口。', self.tray_switch)
        inner_smart.addWidget(row_tray)

        layout.addWidget(frame_smart)

        # 3. Software Auto-Update System
        frame_update, inner_update = card('版本更新', '从 Pointer 的 GitHub Releases 检查新版本。')

        self.auto_update_switch = MacSwitch()
        self.auto_update_switch.setObjectName('autoUpdateCheck')
        self.auto_update_switch.toggled.connect(lambda enabled: owner.change(auto_check_update=enabled))
        row_auto_up = SettingsRow('启动时检查更新', '发现新版本时提示。此开关在应用后生效。', self.auto_update_switch)
        inner_update.addWidget(row_auto_up)

        inner_update.addWidget(HairlineDivider())

        up_box = QWidget()
        up_layout = QHBoxLayout(up_box)
        up_layout.setContentsMargins(0, 0, 0, 0)
        up_layout.setSpacing(10)

        self.check_update_btn = QPushButton('检查更新')
        self.check_update_btn.setObjectName('checkUpdateButton')
        self.check_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_update_btn.clicked.connect(owner.check_updates_interactive)
        up_layout.addWidget(self.check_update_btn)

        self.update_status_lbl = QLabel('当前版本: 检查就绪')
        self.update_status_lbl.setObjectName('updateStatusLabel')

        up_layout.addWidget(self.update_status_lbl, 1)

        row_manual_up = SettingsRow('手动检查', '检查可用版本，不自动安装。', up_box)
        inner_update.addWidget(row_manual_up)

        layout.addWidget(frame_update)

        # 4. Configuration Profiles & Themes
        frame, inner = card('配置与主题', '导入加入草稿；导出保存当前草稿。')

        cfg_box = QWidget()
        cfg_layout = QGridLayout(cfg_box)
        cfg_layout.setContentsMargins(0, 0, 0, 0)
        cfg_layout.setSpacing(8)

        import_theme_btn = QPushButton('导入主题包')
        import_theme_btn.setObjectName('importThemeBtn')
        import_theme_btn.clicked.connect(owner.import_theme_package)
        cfg_layout.addWidget(import_theme_btn, 0, 0)

        export_theme_btn = QPushButton('导出主题包')
        export_theme_btn.setObjectName('exportThemeBtn')
        export_theme_btn.clicked.connect(owner.export_theme_package)
        cfg_layout.addWidget(export_theme_btn, 0, 1)

        import_btn = QPushButton('导入 JSON')
        import_btn.clicked.connect(owner.import_settings)
        cfg_layout.addWidget(import_btn, 1, 0)

        export_btn = QPushButton('导出 JSON')
        export_btn.clicked.connect(owner.export_settings)
        cfg_layout.addWidget(export_btn, 1, 1)

        reset_btn = QPushButton('恢复默认配置')
        reset_btn.clicked.connect(owner.reset_defaults)
        cfg_layout.addWidget(reset_btn, 2, 0)

        row_cfg = SettingsRow('配置文件', '保存或载入颜色、形态与动效设置。', cfg_box)
        inner.addWidget(row_cfg)
        layout.addWidget(frame)

        # 5. Emergency Restore
        frame_rst, inner_rst = card('恢复原光标', '恢复首次应用前保存的原光标备份。')

        restore_btn = QPushButton('恢复 Windows 原生光标')
        restore_btn.setObjectName('restoreButton')
        restore_btn.clicked.connect(owner.confirm_restore)

        row_rst = SettingsRow('恢复原光标', '恢复原光标并关闭 Pointer 开机启动；执行前需要确认。', restore_btn)
        inner_rst.addWidget(row_rst)
        layout.addWidget(frame_rst)

        layout.addStretch()

    def sync(self, settings):
        self.startup.blockSignals(True)
        self.startup.setChecked(settings.startup)
        self.startup.blockSignals(False)

        if hasattr(self, 'shake_switch'):
            self.shake_switch.blockSignals(True)
            self.shake_switch.setChecked(getattr(settings, 'shake_to_find', True))
            self.shake_switch.blockSignals(False)

        if hasattr(self, 'game_switch'):
            self.game_switch.blockSignals(True)
            self.game_switch.setChecked(getattr(settings, 'game_dnd', True))
            self.game_switch.blockSignals(False)

        if hasattr(self, 'tray_switch'):
            self.tray_switch.blockSignals(True)
            self.tray_switch.setChecked(getattr(settings, 'tray_enabled', True))
            self.tray_switch.blockSignals(False)

        if hasattr(self, 'auto_update_switch'):
            self.auto_update_switch.blockSignals(True)
            self.auto_update_switch.setChecked(getattr(settings, 'auto_check_update', True))
            self.auto_update_switch.blockSignals(False)
