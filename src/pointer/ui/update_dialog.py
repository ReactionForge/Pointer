"""Theme-aware update checks and a cancellable download/install handoff."""
import re
import threading
import weakref
from pathlib import Path
from PySide6.QtCore import Qt, Signal, Slot, QObject, QTimer, QEvent, QUrl
from PySide6.QtGui import QPixmap, QPalette, QColor, QDesktopServices, QTextOption
from PySide6.QtWidgets import (
    QApplication, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTextBrowser, QPlainTextEdit, QSizePolicy,
)
from pointer.paths import DATA_ROOT, ROOT, INSTALL_ROOT
from pointer.updater import download_update_package, trigger_silent_upgrade, UpdateError, ChecksumMismatchError
from .colors import theme_colors
from .theme import scrollbar_style


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

    def __init__(self, url, destination, expected_sha256=None, *, expected_size=None):
        super().__init__()
        self.url = url
        self.destination = destination
        self.expected_sha256 = expected_sha256
        self.expected_size = expected_size
        self.failure_stage = '下载失败'
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
                self.url, self.destination, expected_sha256=self.expected_sha256,
                expected_size=self.expected_size,
                progress_callback=lambda done, total: self.progress.emit(done, total),
                cancel_flag=self._cancelled.is_set,
            )
            if not self._cancelled.is_set():
                self.finished.emit(str(self.destination))
        except Exception as error:
            self.failure_stage = '完整性校验失败' if isinstance(error, ChecksumMismatchError) else '下载失败'
            if not self._cancelled.is_set():
                try:
                    self.failed.emit(str(error))
                except RuntimeError:
                    pass  # The dialog and its signal receiver were already destroyed.


class UpdateDialog(QDialog):
    """Keep update stages, failure details and cancellation visible in both themes."""
    def __init__(self, update_info, application=None, parent=None):
        super().__init__(parent)
        self.update_info = dict(update_info)
        self.application = application
        self.worker = None
        self._closed = False
        self._downloaded_installer = None
        self.stage = 'ready'
        self.ui_dark = bool(getattr(parent, 'ui_dark', False))
        self.colors = getattr(parent, 'confirmation_colors', theme_colors(self.ui_dark))
        self.can_auto_install = self._has_install_metadata()

        self.setWindowTitle(f"软件更新 · Pointer v{update_info.get('latest_version')}")
        self.setMinimumSize(440, 460)
        self.resize(600, 560)
        self.setSizeGripEnabled(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._apply_theme()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(12)
        header = QHBoxLayout()
        header.setSpacing(14)
        icon_lbl = QLabel()
        icon_path = next((path for path in (
            ROOT / 'pointer.ico', ROOT / 'packaging' / 'windows' / 'pointer.ico',
            INSTALL_ROOT / 'pointer.ico',
        ) if path.exists()), None)
        if icon_path:
            icon_lbl.setPixmap(QPixmap(str(icon_path)).scaled(
                44, 44, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(icon_lbl)
        title_box = QVBoxLayout()
        title = self._label(f"发现新版本 Pointer v{update_info.get('latest_version')}")
        title.setStyleSheet('font-size: 16px; font-weight: 600;')
        title_box.addWidget(title)
        meta = self._label(f"当前版本 v{update_info.get('current_version', '—')} · 发布日期 {update_info.get('published_at') or '未知'}")
        meta.setStyleSheet(f"color: {self.colors['muted']}; font-size: 12px;")
        title_box.addWidget(meta)
        header.addLayout(title_box, 1)
        layout.addLayout(header)
        layout.addWidget(self._label('更新内容与改进'))
        self.notes_browser = QTextBrowser()
        self.notes_browser.setOpenExternalLinks(True)
        self.notes_browser.setMarkdown(update_info.get('release_notes') or '暂无详细更新说明。')
        self.notes_browser.setMinimumHeight(80)
        layout.addWidget(self.notes_browser, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        self.status_lbl = self._label('')
        layout.addWidget(self.status_lbl)
        self.error_details = QPlainTextEdit()
        self.error_details.setReadOnly(True)
        self.error_details.setAccessibleName('更新错误详情')
        self.error_details.setWordWrapMode(QTextOption.WrapMode.WrapAnywhere)
        self.error_details.setMinimumHeight(70)
        self.error_details.setMaximumHeight(150)
        self.error_details.hide()
        layout.addWidget(self.error_details)
        self.copy_error_btn = QPushButton('复制错误详情')
        self.copy_error_btn.clicked.connect(lambda: QApplication.clipboard().setText(self.error_details.toPlainText()))
        self.copy_error_btn.hide()
        layout.addWidget(self.copy_error_btn, 0, Qt.AlignmentFlag.AlignLeft)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.skip_btn = QPushButton('跳过此版本')
        self.skip_btn.clicked.connect(self._skip_version)
        buttons.addWidget(self.skip_btn)
        buttons.addStretch()
        self.later_btn = QPushButton('稍后提醒')
        self.later_btn.clicked.connect(self.reject)
        buttons.addWidget(self.later_btn)
        self.update_btn = QPushButton('下载并更新' if self.can_auto_install else '手动下载')
        self.update_btn.setObjectName('primaryButton')
        self.update_btn.clicked.connect(self._start_download)
        self.update_btn.setDefault(True)
        buttons.addWidget(self.update_btn)
        layout.addLayout(buttons)
        if self.can_auto_install:
            self._set_status('ready', '下载后校验安装包，确认草稿已处理后启动安装器。')
        else:
            self._set_status('manual', '此发布缺少有效安装包、可信 SHA-256 或大小，无法自动更新。请前往发布页手动下载。')

    @staticmethod
    def _label(text):
        label = QLabel(text)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        return label

    def _has_install_metadata(self):
        info = self.update_info
        digest = info.get('expected_sha256')
        size = info.get('asset_size')
        url = info.get('download_url')
        name = info.get('asset_name')
        return bool(info.get('can_auto_install', True) and isinstance(digest, str)
                    and re.fullmatch(r'[0-9a-fA-F]{64}', digest)
                    and type(size) is int and size > 0
                    and isinstance(url, str) and url.startswith('https://')
                    and isinstance(name, str) and name and Path(name).name == name)

    def _apply_theme(self):
        c = self.colors
        palette = QPalette(self.palette())
        for role, key in ((QPalette.ColorRole.Window, 'canvas'), (QPalette.ColorRole.WindowText, 'text'),
                          (QPalette.ColorRole.Base, 'surface'), (QPalette.ColorRole.Text, 'text'),
                          (QPalette.ColorRole.Button, 'raised'), (QPalette.ColorRole.ButtonText, 'text'),
                          (QPalette.ColorRole.Highlight, 'selected'), (QPalette.ColorRole.HighlightedText, 'selected_text')):
            palette.setColor(role, QColor(c[key]))
        self.setPalette(palette)
        self.setStyleSheet(f"""
            QDialog {{ background: {c['canvas']}; color: {c['text']}; }}
            QLabel {{ color: {c['text']}; font-size: 13px; }}
            QTextBrowser, QPlainTextEdit {{ background: {c['surface']}; color: {c['text']};
                border: 1px solid {c['divider']}; border-radius: 8px; padding: 8px; font-size: 13px; }}
            QProgressBar {{ background: {c['raised']}; border: none; border-radius: 4px; height: 8px; }}
            QProgressBar::chunk {{ background: {c['selected']}; border-radius: 4px; }}
            QPushButton {{ background: {c['raised']}; color: {c['text']}; border: 1px solid {c['border']};
                border-radius: 8px; padding: 7px 12px; font-size: 13px; }}
            QPushButton:hover {{ background: {c['surface']}; }}
            QPushButton:focus {{ border: 2px solid {c['focus']}; }}
            QPushButton:disabled {{ color: {c['disabled_text']}; border-color: {c['divider']}; }}
            QPushButton#primaryButton {{ background: {c['selected']}; color: {c['selected_text']}; font-weight: 600; }}
        """ + scrollbar_style(self.ui_dark))

    def _set_status(self, stage, text, *, error=False):
        self.stage = stage
        self.status_lbl.setText(text)
        self.status_lbl.setStyleSheet(f"color: {self.colors['danger' if error else 'muted']}; font-size: 13px;")

    def _clear_error(self):
        self.error_details.clear()
        self.error_details.hide()
        self.copy_error_btn.hide()

    def _show_error(self, stage, title, error):
        self._set_status(stage, title + '，请查看下方详情。', error=True)
        self.error_details.setPlainText(str(error))
        self.error_details.show()
        self.copy_error_btn.show()
        self.update_btn.setEnabled(True)
        self.update_btn.setText('重试安装' if self._downloaded_installer else '重试下载' if self.can_auto_install else '手动下载')
        self.later_btn.setEnabled(True)
        self.later_btn.setText('返回工作台' if stage == 'preflight' else '稍后提醒')
        self.skip_btn.setEnabled(True)
        self.progress_bar.hide()

    def _skip_version(self):
        if self._closed:
            return
        try:
            parent = self.parent()
            if parent is None or not callable(getattr(parent, 'save_skipped_update', None)):
                raise RuntimeError('请在工作台内保存更新偏好。')
            parent.save_skipped_update(self.update_info.get('latest_version'))
        except Exception as error:
            self._show_error('preference', '跳过版本未保存，可点击“跳过此版本”重试', error)
            return
        self.reject()

    def _open_manual_download(self):
        url = QUrl(self.update_info.get('html_url') or 'https://github.com/ReactionForge/Pointer/releases')
        if url.scheme() != 'https' or not url.host() or not QDesktopServices.openUrl(url):
            self._show_error('manual', '发布页打开失败', '请在浏览器中打开 Pointer 的 GitHub 发布页。')

    def _start_download(self):
        if self._closed or (self.worker and self.worker.isRunning()):
            return
        self._clear_error()
        if not self.can_auto_install:
            self._open_manual_download()
            return
        if self._downloaded_installer:
            self._attempt_install()
            return
        if not self._check_preflight():
            return
        self.update_btn.setEnabled(False)
        self.skip_btn.setEnabled(False)
        self.later_btn.setText('取消下载')
        self.progress_bar.setRange(0, 0)
        self.progress_bar.show()
        self._set_status('downloading', '正在连接下载服务器… 可取消下载。')
        target_path = DATA_ROOT / 'updates' / self.update_info['expected_sha256'].lower() / self.update_info['asset_name']
        self.worker = DownloadWorker(
            self.update_info['download_url'], target_path,
            expected_sha256=self.update_info['expected_sha256'], expected_size=self.update_info['asset_size'],
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
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(min(100, int(done * 100 / total)))
            self._set_status('verifying' if done >= total else 'downloading',
                             '下载完成，正在校验完整性…' if done >= total else
                             f'正在下载安装包… {done / (1024 * 1024):.1f} MB / {total / (1024 * 1024):.1f} MB')
        else:
            self._set_status('downloading', f'已下载 {done / (1024 * 1024):.1f} MB…')

    @Slot(str)
    def _on_download_finished(self, installer_path):
        if self._closed:
            return
        if not self.can_auto_install:
            self._set_status('manual', '缺少可信校验信息，自动安装已取消。请手动下载。')
            return
        self._downloaded_installer = installer_path
        self._attempt_install()

    def _check_preflight(self):
        parent = self.parent()
        if parent is None or not callable(getattr(parent, '_ready_for_upgrade', None)):
            reason = '无法确认工作台状态，请返回工作台重试。'
        elif not parent._ready_for_upgrade():
            reason = parent.upgrade_block_reason()
        else:
            reason = ''
        if reason:
            self._show_error('preflight', '暂不能升级', reason)
            return False
        return True

    def _attempt_install(self):
        if self._closed or not self._check_preflight():
            return
        parent = self.parent()
        self._clear_error()
        self._set_status('launching', '完整性校验通过，正在启动安装器…')
        try:
            # The installer alone owns stop/deploy/resume; launch failure changes no runtime state.
            trigger_silent_upgrade(self._downloaded_installer, self.application,
                                   expected_sha256=self.update_info['expected_sha256'],
                                   expected_size=self.update_info['asset_size'])
        except FileNotFoundError as error:
            if not Path(self._downloaded_installer).is_file():
                self._downloaded_installer = None
                self._show_error('download', '安装包已丢失，请重新下载', error)
            else:
                self._show_error('launch', '安装器启动失败', error)
            return
        except UpdateError as error:
            self._downloaded_installer = None
            self._show_error('verification', '安装包校验失败', error)
            return
        except Exception as error:
            self._show_error('launch', '安装器启动失败', error)
            return
        self._set_status('launched', '安装器已启动，正在关闭工作台。')
        self.accept()
        parent._finish_upgrade()

    @Slot(str)
    def _on_download_failed(self, error):
        if not self._closed:
            title = getattr(self.worker, 'failure_stage', '下载失败')
            self._show_error('verification' if title == '完整性校验失败' else 'download', title, error)

    def done(self, result):
        self._closed = True
        if self.worker and self.worker.isRunning():
            self.worker.cancel()
        super().done(result)
