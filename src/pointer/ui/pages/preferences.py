from PySide6.QtWidgets import QWidget, QVBoxLayout, QCheckBox, QPushButton, QHBoxLayout
from ..theme import card


class PreferencesPage(QWidget):
    def __init__(self, owner):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0,0,0,0)
        frame, inner = card('运行与启动', '关闭设置窗口后，已启用的光标效果继续运行。')
        self.startup = QCheckBox('登录 Windows 时启动光标效果')
        self.startup.setObjectName('startupCheck')
        self.startup.toggled.connect(lambda enabled: owner.run_operation(lambda: owner.application.set_startup(enabled), '开机启动设置已更新'))
        inner.addWidget(self.startup)
        row = QHBoxLayout()
        for text, name, method in [('暂停效果','pauseButton','pause'),('恢复运行','resumeButton','resume')]:
            button = QPushButton(text)
            button.setObjectName(name)
            button.clicked.connect(lambda checked=False, method=method: owner.run_operation(getattr(owner.application,method), '运行状态已更新'))
            row.addWidget(button)
        inner.addLayout(row)
        layout.addWidget(frame)
        frame, inner = card('配置文件', '导入会更新预览草稿，点击“应用配置”后才改变系统光标。')
        row = QHBoxLayout()
        for text, callback in [('导入配置',owner.import_settings),('导出配置',owner.export_settings),('默认配置',owner.reset_defaults)]:
            button = QPushButton(text)
            button.clicked.connect(callback)
            row.addWidget(button)
        inner.addLayout(row)
        layout.addWidget(frame)
        frame, inner = card('恢复原光标', '恢复最初的 Windows 光标并关闭 Pointer 开机启动，保留自定义配置。')
        button = QPushButton('恢复 Windows 原光标')
        button.clicked.connect(owner.confirm_restore)
        inner.addWidget(button)
        layout.addWidget(frame)
        layout.addStretch()

    def sync(self, settings):
        self.startup.blockSignals(True)
        self.startup.setChecked(settings.startup)
        self.startup.blockSignals(False)
