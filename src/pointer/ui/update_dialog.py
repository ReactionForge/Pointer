"""macOS Acrylic styled Update Dialog for Pointer."""
import os
from pathlib import Path
from PySide6.QtCore import Qt, QThread, Signal, Slot
from PySide6.QtGui import QIcon, QPixmap, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextBrowser, QFrame
)
from pointer.paths import DATA_ROOT, ROOT, INSTALL_ROOT
from pointer.updater import download_update_package, trigger_silent_upgrade, UpdateError


class DownloadWorker(QThread):
    progress = Signal(int, int)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, url, destination, expected_sha256=None):
        super().__init__()
        self.url = url
        self.destination = destination
        self.expected_sha256 = expected_sha256
        self._cancelled = False

    def cancel(self):
        self._cancelled = True

    def run(self):
        try:
            sha256 = download_update_package(
                self.url,
                self.destination,
                expected_sha256=self.expected_sha256,
                progress_callback=lambda done, total: self.progress.emit(done, total),
                cancel_flag=lambda: self._cancelled,
            )
            self.finished.emit(str(self.destination))
        except Exception as error:
            self.failed.emit(str(error))


class UpdateDialog(QDialog):
    """macOS-styled floating acrylic update modal."""
    def __init__(self, update_info, application=None, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.application = application
        self.worker = None

        self.setWindowTitle(f"软件更新 · Pointer v{update_info.get('latest_version')}")
        self.setFixedSize(540, 480)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e20;
                color: #f5f5f7;
            }
            QLabel {
                color: #f5f5f7;
            }
            QTextBrowser {
                background-color: rgba(0, 0, 0, 0.25);
                border: 0.5px solid rgba(255, 255, 255, 0.12);
                border-radius: 8px;
                padding: 10px;
                color: #e5e5ea;
                font-size: 12.5px;
            }
            QProgressBar {
                background-color: rgba(255, 255, 255, 0.08);
                border: none;
                border-radius: 4px;
                height: 8px;
                text-align: center;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #007aff, stop:1 #34c759);
                border-radius: 4px;
            }
            QPushButton {
                background-color: rgba(255, 255, 255, 0.08);
                border: 0.5px solid rgba(255, 255, 255, 0.14);
                border-radius: 8px;
                padding: 7px 16px;
                color: #f5f5f7;
                font-weight: 500;
                font-size: 12.5px;
            }
            QPushButton:hover {
                background-color: rgba(255, 255, 255, 0.14);
            }
            QPushButton#primaryButton {
                background-color: #007aff;
                border: none;
                color: #ffffff;
                font-weight: 600;
            }
            QPushButton#primaryButton:hover {
                background-color: #0062cc;
            }
            QPushButton#subtleButton {
                background-color: transparent;
                border: none;
                color: #86868b;
                font-size: 11.5px;
            }
            QPushButton#subtleButton:hover {
                color: #f5f5f7;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        # Header Cluster
        header = QHBoxLayout()
        header.setSpacing(14)

        icon_lbl = QLabel()
        icon_path = None
        for candidate in (
            ROOT / 'pointer.ico',
            ROOT / 'packaging' / 'windows' / 'pointer.ico',
            INSTALL_ROOT / 'pointer.ico',
        ):
            if candidate.exists():
                icon_path = candidate
                break
        if icon_path:
            icon_lbl.setPixmap(QPixmap(str(icon_path)).scaled(44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(icon_lbl)

        title_box = QVBoxLayout()
        title_box.setSpacing(3)
        title_lbl = QLabel(f"发现新版本 Pointer v{update_info.get('latest_version')}")
        title_lbl.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        title_box.addWidget(title_lbl)

        meta_lbl = QLabel(f"当前版本: v{update_info.get('current_version')} · 发布日期: {update_info.get('published_at')}")
        meta_lbl.setStyleSheet("font-size: 11.5px; color: #86868b;")
        title_box.addWidget(meta_lbl)
        header.addLayout(title_box, 1)

        layout.addLayout(header)

        # Release Notes Label & Browser
        notes_lbl = QLabel("更新内容与改进：")
        notes_lbl.setStyleSheet("font-weight: 600; font-size: 12px; color: #c7c7cc;")
        layout.addWidget(notes_lbl)

        self.notes_browser = QTextBrowser()
        self.notes_browser.setOpenExternalLinks(True)
        raw_notes = update_info.get("release_notes", "") or "暂无详细更新说明。"
        self.notes_browser.setMarkdown(raw_notes)
        layout.addWidget(self.notes_browser, 1)

        # Download Progress Area (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)

        self.status_lbl = QLabel("")
        self.status_lbl.setStyleSheet("color: #86868b; font-size: 11.5px;")
        layout.addWidget(self.status_lbl)

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.skip_btn = QPushButton("跳过此版本")
        self.skip_btn.setObjectName("subtleButton")
        self.skip_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.skip_btn.clicked.connect(self._skip_version)
        btn_layout.addWidget(self.skip_btn)

        btn_layout.addStretch()

        self.later_btn = QPushButton("稍后提醒")
        self.later_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.later_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.later_btn)

        self.update_btn = QPushButton("立即更新")
        self.update_btn.setObjectName("primaryButton")
        self.update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.update_btn.clicked.connect(self._start_download)
        btn_layout.addWidget(self.update_btn)

        layout.addLayout(btn_layout)

    def _skip_version(self):
        latest = self.update_info.get("latest_version")
        if self.parent() and hasattr(self.parent(), "change"):
            self.parent().change(skip_update_version=latest)
        self.reject()

    def _start_download(self):
        download_url = self.update_info.get("download_url")
        if not download_url:
            self.status_lbl.setText("未找到有效安装包资源，请前往 GitHub 手动下载。")
            self.status_lbl.setStyleSheet("color: #ff453a; font-size: 11.5px;")
            return

        self.update_btn.setEnabled(False)
        self.later_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.progress_bar.show()
        self.status_lbl.setText("正在连接下载服务器…")
        self.status_lbl.setStyleSheet("color: #007aff; font-size: 11.5px;")

        updates_dir = DATA_ROOT / "updates"
        asset_name = self.update_info.get("asset_name") or f"Pointer-v{self.update_info.get('latest_version')}-setup.exe"
        target_path = updates_dir / asset_name

        self.worker = DownloadWorker(
            download_url,
            target_path,
            expected_sha256=self.update_info.get("expected_sha256")
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_download_finished)
        self.worker.failed.connect(self._on_download_failed)
        self.worker.start()

    @Slot(int, int)
    def _on_progress(self, done, total):
        if total > 0:
            percent = int(done * 100 / total)
            self.progress_bar.setValue(percent)
            mb_done = done / (1024 * 1024)
            mb_total = total / (1024 * 1024)
            self.status_lbl.setText(f"正在安全下载安装包… {mb_done:.1f} MB / {mb_total:.1f} MB ({percent}%)")
        else:
            self.status_lbl.setText(f"已下载 {done / (1024 * 1024):.1f} MB…")

    @Slot(str)
    def _on_download_finished(self, installer_path):
        self.status_lbl.setText("下载完成，完整性校验通过。正在启动静默更新…")
        self.status_lbl.setStyleSheet("color: #34c759; font-size: 11.5px;")
        try:
            trigger_silent_upgrade(installer_path, self.application)
            from PySide6.QtWidgets import QApplication
            app = QApplication.instance()
            if app:
                app.quit()
        except Exception as error:
            self._on_download_failed(f"启动升级程序失败：{error}")

    @Slot(str)
    def _on_download_failed(self, error):
        self.status_lbl.setText(f"下载失败：{error}")
        self.status_lbl.setStyleSheet("color: #ff453a; font-size: 11.5px;")
        self.update_btn.setEnabled(True)
        self.later_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.progress_bar.hide()

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
            self.worker.wait(1000)
        super().closeEvent(event)
