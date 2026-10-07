"""macOS Acrylic styled Update Dialog for Pointer."""
import os
import threading
import weakref
from pathlib import Path
from PySide6.QtCore import Qt, Signal, Slot, QObject, QTimer, QEvent
from PySide6.QtGui import QIcon, QPixmap, QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextBrowser, QFrame
)
from pointer.paths import DATA_ROOT, ROOT, INSTALL_ROOT
from pointer.updater import download_update_package, trigger_silent_upgrade, UpdateError


UPDATE_CHECK_TIMEOUT_MS = 10000


class UpdateCheck(QObject):
    """Deliver network results through a GUI-owned signal receiver and deadline."""
    completed = Signal(object, str, bool)
    cancelled = Signal(bool)
    _returned = Signal(int, object, str)

    def __init__(self, window):
        super().__init__(window)
        self.running = False
        self._serial = 0
        self._interactive = False
        self._cancel_event = None
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.setInterval(UPDATE_CHECK_TIMEOUT_MS)
        self.deadline.timeout.connect(self._timed_out)
        self._returned.connect(self._accept_result, Qt.ConnectionType.QueuedConnection)
        window.installEventFilter(self)

    def start(self, current_version, *, interactive=False):
        if self.running:
            self._interactive |= interactive
            return
        self._serial += 1
        serial = self._serial
        self.running = True
        self._interactive = interactive
        self._cancel_event = cancelled = threading.Event()
        receiver = weakref.ref(self)
        self.deadline.start()

        def check():
            info, error = None, ''
            try:
                from pointer.updater import check_for_updates
                info = check_for_updates(current_version)
                if not isinstance(info, dict):
                    raise ValueError('更新服务返回了无效结果')
            except Exception as caught:
                error = str(caught) or type(caught).__name__
            if cancelled.is_set():
                return
            bridge = receiver()
            if bridge is not None:
                try:
                    bridge._returned.emit(serial, info, error)
                except RuntimeError:
                    # The parent window may have been deleted during the request.
                    pass

        threading.Thread(target=check, name='Pointer-update-check', daemon=True).start()

    @Slot(int, object, str)
    def _accept_result(self, serial, info, error):
        if not self.running or serial != self._serial:
            return
        self.deadline.stop()
        self.running = False
        self._cancel_event.set()
        self.completed.emit(info, error, self._interactive)

    @Slot()
    def _timed_out(self):
        self._accept_result(self._serial, None, '检查超时，请检查网络后重试。')

    def cancel(self):
        if not self.running:
            return
        self.deadline.stop()
        self.running = False
        self._serial += 1
        self._cancel_event.set()
        self.cancelled.emit(self._interactive)

    def eventFilter(self, watched, event):
        # Accepted closes hide the window; rejected dirty-close prompts do not.
        # Spontaneous hides (minimizing on Windows) leave the request active.
        if watched is self.parent() and event.type() == QEvent.Type.Hide and not event.spontaneous():
            self.cancel()
        return super().eventFilter(watched, event)


class DownloadWorker(QObject):
    progress = Signal(int, int)
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, url, destination, expected_sha256=None):
        super().__init__()
        self.url = url
        self.destination = destination
        self.expected_sha256 = expected_sha256
        self._cancelled = threading.Event()
        self._thread = None

    def start(self):
        # Network reads may outlive the dialog; a daemon thread never owns Qt UI.
        self._thread = threading.Thread(target=self.run, name='Pointer-update-download', daemon=True)
        self._thread.start()

    def isRunning(self):
        return self._thread is not None and self._thread.is_alive()

    def cancel(self):
        self._cancelled.set()

    def run(self):
        try:
            download_update_package(
                self.url,
                self.destination,
                expected_sha256=self.expected_sha256,
                progress_callback=lambda done, total: self.progress.emit(done, total),
                cancel_flag=self._cancelled.is_set,
            )
            if not self._cancelled.is_set():
                self.finished.emit(str(self.destination))
        except Exception as error:
            if not self._cancelled.is_set():
                self.failed.emit(str(error))


class UpdateDialog(QDialog):
    """macOS-styled floating acrylic update modal."""
    def __init__(self, update_info, application=None, parent=None):
        super().__init__(parent)
        self.update_info = update_info
        self.application = application
        self.worker = None
        self._closed = False

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
        if self._closed or (self.worker and self.worker.isRunning()):
            return
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
        if self._closed:
            return
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
        if self._closed:
            return
        status = ('下载完成，完整性校验通过。正在启动静默更新…'
                  if self.update_info.get('expected_sha256') else '下载完成，正在启动静默更新…')
        self.status_lbl.setText(status)
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
        if self._closed:
            return
        self.status_lbl.setText(f"下载失败：{error}")
        self.status_lbl.setStyleSheet("color: #ff453a; font-size: 11.5px;")
        self.update_btn.setEnabled(True)
        self.later_btn.setEnabled(True)
        self.skip_btn.setEnabled(True)
        self.progress_bar.hide()

    def done(self, result):
        self._closed = True
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
        super().done(result)
