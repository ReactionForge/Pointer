from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QCheckBox, QPushButton, QHBoxLayout, QLabel, QFrame
)
from ..theme import card


class PreferencesPage(QWidget):
    """System & Preferences: Startup self-healing, profile backups, and background service."""
    def __init__(self, owner):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # 1. Service Runtime & Startup
        frame, inner = card('⚙️ 系统运行与开机启动自愈', '关闭设置窗口后，Pointer 后台光标增强引擎将继续保持高效低耗常驻运行。')

        startup_box = QFrame()
        startup_box.setStyleSheet('QFrame { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 11px; padding: 12px; }')
        startup_layout = QVBoxLayout(startup_box)
        startup_layout.setContentsMargins(10, 8, 10, 8)
        startup_layout.setSpacing(6)

        self.startup = QCheckBox('登录 Windows 时自动启动自适应光标')
        self.startup.setObjectName('startupCheck')
        self.startup.toggled.connect(
            lambda enabled: owner.run_operation(lambda: owner.application.set_startup(enabled), '开机启动设置已更新')
        )
        startup_layout.addWidget(self.startup)

        startup_hint = QLabel('启用后将在系统开机登录时自动常驻后台，无感知轻量化启动，不增加系统开销。')
        startup_hint.setStyleSheet('color: #64748b; font-size: 11px;')
        startup_layout.addWidget(startup_hint)
        inner.addWidget(startup_box)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        for text, name, method in [
            ('⏸  临时暂停光标效果', 'pauseButton', 'pause'),
            ('▶  恢复光标运行', 'resumeButton', 'resume'),
        ]:
            button = QPushButton(text)
            button.setObjectName(name)
            button.clicked.connect(
                lambda checked=False, method=method: owner.run_operation(getattr(owner.application, method), '运行状态已更新')
            )
            btn_row.addWidget(button)
        inner.addLayout(btn_row)
        layout.addWidget(frame)

        # 2. Configuration Profiles
        frame, inner = card('💾 配置文件备份与重置', '导入将更新预览草稿，点击底栏“应用配置”后正式写入 Windows 系统。')
        cfg_row = QHBoxLayout()
        cfg_row.setSpacing(10)
        for text, callback in [
            ('📂  导入配置 (JSON)', owner.import_settings),
            ('💾  导出当前配置', owner.export_settings),
            ('↺  恢复默认配置', owner.reset_defaults),
        ]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            cfg_row.addWidget(button)
        inner.addLayout(cfg_row)
        layout.addWidget(frame)

        # 3. Emergency Restore
        frame, inner = card('🛡️ 恢复 Windows 原生光标', '一键彻底还原 Windows 初始光标方案并清除自启动注册，用户个性化备份仍将安全保留。')
        restore_btn = QPushButton('🛡️  恢复 Windows 原生光标')
        restore_btn.setStyleSheet('''
            QPushButton {
                background-color: rgba(225, 29, 72, 0.12);
                border: 1px solid rgba(225, 29, 72, 0.35);
                color: #fb7185;
                font-weight: 700;
                padding: 10px 16px;
                border-radius: 9px;
            }
            QPushButton:hover {
                background-color: rgba(225, 29, 72, 0.22);
                border-color: #f43f5e;
                color: #ffffff;
            }
        ''')
        restore_btn.clicked.connect(owner.confirm_restore)
        inner.addWidget(restore_btn)
        layout.addWidget(frame)

        layout.addStretch()

    def sync(self, settings):
        self.startup.blockSignals(True)
        self.startup.setChecked(settings.startup)
        self.startup.blockSignals(False)
