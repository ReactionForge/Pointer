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

        # 2. Configuration Profiles
        frame, inner = card('配置文件备份与重置', '导入将更新预览草稿，点击底栏“应用配置”后正式写入 Windows 系统。')

        cfg_box = QWidget()
        cfg_layout = QHBoxLayout(cfg_box)
        cfg_layout.setContentsMargins(0, 0, 0, 0)
        cfg_layout.setSpacing(8)

        import_btn = QPushButton('导入配置 (JSON)')
        import_btn.clicked.connect(owner.import_settings)
        cfg_layout.addWidget(import_btn)

        export_btn = QPushButton('导出当前配置')
        export_btn.clicked.connect(owner.export_settings)
        cfg_layout.addWidget(export_btn)

        reset_btn = QPushButton('恢复默认配置')
        reset_btn.clicked.connect(owner.reset_defaults)
        cfg_layout.addWidget(reset_btn)

        row_cfg = SettingsRow('配置数据备份与恢复', '保存个性化配色与动效参数备份至本地文件，或恢复出厂预设', cfg_box)
        inner.addWidget(row_cfg)
        layout.addWidget(frame)

        # 3. Emergency Restore
        frame, inner = card('恢复 Windows 原生光标', '一键彻底还原 Windows 初始光标方案并清除自启动注册，用户个性化备份仍将安全保留。')

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
        inner.addWidget(row_rst)
        layout.addWidget(frame)

        layout.addStretch()

    def sync(self, settings):
        self.startup.blockSignals(True)
        self.startup.setChecked(settings.startup)
        self.startup.blockSignals(False)
