from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QHBoxLayout, QLabel, QFrame
)
from ..theme import card, SettingsRow, HairlineDivider, MacSwitch


class PreferencesPage(QWidget):
    """System & Preferences: Startup self-healing, profile backups, and background service."""
    def __init__(self, owner):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        # 1. Service Runtime & Startup
        frame, inner = card('系统运行与开机启动自愈', '关闭设置窗口后，Pointer 后台光标增强引擎将继续保持高效低耗常驻运行。')

        # Row 1: Startup switch
        self.startup = MacSwitch()
        self.startup.setObjectName('startupCheck')
        self.startup.toggled.connect(
            lambda enabled: owner.run_operation(lambda: owner.application.set_startup(enabled), '开机启动设置已更新')
        )
        row1 = SettingsRow('登录 Windows 时自动启动自适应光标', '开机登录系统时自动常驻后台，无感知轻量化启动，不增加系统开销', self.startup)
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

        row2 = SettingsRow('光标增强引擎状态', '临时暂停拦截以比对 Windows 原生光标，或恢复自适应接管', btn_box)
        inner.addWidget(row2)
        layout.addWidget(frame)

        # 2. Smart Enhancements & Focus Experience
        frame_smart, inner_smart = card('智能系统增强与专注体验', '深度融合 macOS 经典微交互与 Windows 全屏环境智能识别。')

        self.shake_switch = MacSwitch()
        self.shake_switch.setObjectName('shakeCheck')
        self.shake_switch.toggled.connect(lambda enabled: owner.change(shake_to_find=enabled))
        row_shake = SettingsRow('晃动放大寻针 (macOS Shake-to-Find)', '快速晃动鼠标瞬间放大至 2.5 倍以极速定位指针，摇晃停止后平滑弹性复位', self.shake_switch)
        inner_smart.addWidget(row_shake)

        inner_smart.addWidget(HairlineDivider())

        self.game_switch = MacSwitch()
        self.game_switch.setObjectName('gameCheck')
        self.game_switch.toggled.connect(lambda enabled: owner.change(game_dnd=enabled))
        row_game = SettingsRow('全屏应用与游戏智能免打扰', '智能感知全屏独占游戏或专业应用，自动暂停拦截放行原始手感，切换即自愈', self.game_switch)
        inner_smart.addWidget(row_game)

        inner_smart.addWidget(HairlineDivider())

        self.tray_switch = MacSwitch()
        self.tray_switch.setObjectName('trayCheck')
        self.tray_switch.toggled.connect(lambda enabled: owner.change(tray_enabled=enabled))
        row_tray = SettingsRow('Windows 任务栏系统托盘极简控制器', '常驻右下角任务栏托盘，提供极简面板与一键切换外观/动效/状态', self.tray_switch)
        inner_smart.addWidget(row_tray)

        layout.addWidget(frame_smart)

        # 3. Software Auto-Update System
        frame_update, inner_update = card('软件更新与版本检测', '基于 GitHub 官方 Releases 渠道与 SemVer 语义化检测，支持静默安全热升级。')

        self.auto_update_switch = MacSwitch()
        self.auto_update_switch.setObjectName('autoUpdateCheck')
        self.auto_update_switch.toggled.connect(lambda enabled: owner.change(auto_check_update=enabled))
        row_auto_up = SettingsRow('启动时后台自动检测新版本', '静默检查发布动态，发现新版本时弹出拟真毛玻璃更新日志，无需频繁手动跟进', self.auto_update_switch)
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
        self.update_status_lbl.setStyleSheet('color: #86868b; font-size: 12px;')
        up_layout.addWidget(self.update_status_lbl, 1)

        row_manual_up = SettingsRow('手动检查新版本', '实时获取最新发布动态与完整静默安装包', up_box)
        inner_update.addWidget(row_manual_up)

        layout.addWidget(frame_update)

        # 4. Configuration Profiles & Themes
        frame, inner = card('主题包与配置备份共享', '支持单文件主题包 (.pointertheme) 自由导出、分发与导入，所见即所得。')

        cfg_box = QWidget()
        cfg_layout = QHBoxLayout(cfg_box)
        cfg_layout.setContentsMargins(0, 0, 0, 0)
        cfg_layout.setSpacing(8)

        import_theme_btn = QPushButton('导入主题包 (.pointertheme)')
        import_theme_btn.setObjectName('importThemeBtn')
        import_theme_btn.clicked.connect(owner.import_theme_package)
        cfg_layout.addWidget(import_theme_btn)

        export_theme_btn = QPushButton('导出主题包 (.pointertheme)')
        export_theme_btn.setObjectName('exportThemeBtn')
        export_theme_btn.clicked.connect(owner.export_theme_package)
        cfg_layout.addWidget(export_theme_btn)

        import_btn = QPushButton('导入 JSON')
        import_btn.clicked.connect(owner.import_settings)
        cfg_layout.addWidget(import_btn)

        export_btn = QPushButton('导出 JSON')
        export_btn.clicked.connect(owner.export_settings)
        cfg_layout.addWidget(export_btn)

        reset_btn = QPushButton('恢复默认配置')
        reset_btn.clicked.connect(owner.reset_defaults)
        cfg_layout.addWidget(reset_btn)

        row_cfg = SettingsRow('配置数据备份与恢复', '保存个性化配色、形态与动效参数备份至本地文件，或恢复出厂预设', cfg_box)
        inner.addWidget(row_cfg)
        layout.addWidget(frame)

        # 5. Emergency Restore
        frame_rst, inner_rst = card('恢复 Windows 原生光标', '一键彻底还原 Windows 初始光标方案并清除自启动注册，用户个性化备份仍将安全保留。')

        restore_btn = QPushButton('恢复 Windows 原生光标')
        restore_btn.setObjectName('restoreButton')
        restore_btn.setStyleSheet('''
            QPushButton#restoreButton {
                background-color: rgba(255, 69, 58, 0.12);
                border: 0.5px solid rgba(255, 69, 58, 0.35);
                color: #ff453a;
                font-weight: 600;
                padding: 7px 16px;
                border-radius: 7px;
            }
            QPushButton#restoreButton:hover {
                background-color: rgba(255, 69, 58, 0.22);
                border-color: #ff453a;
                color: #ffffff;
            }
        ''')
        restore_btn.clicked.connect(owner.confirm_restore)

        row_rst = SettingsRow('系统光标彻底还原', '卸载增强注册表劫持，彻底恢复微软初始光标方案', restore_btn)
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
