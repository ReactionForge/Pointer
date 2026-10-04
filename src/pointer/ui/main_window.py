"""Modern Fluent Obsidian Studio MainWindow for Pointer."""
from dataclasses import replace
import json
import sys
from PySide6.QtCore import Qt, QThread, QTimer, Slot, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QScrollArea, QFileDialog, QMessageBox,
    QGraphicsOpacityEffect
)
from pointer.cursor.settings import CursorSettings, _write_json
from pointer.paths import DATA_ROOT, INSTALL_ROOT, ROOT
from .theme import STYLE, initialize_fonts
from .preview import PreviewPanel
from .workers import Worker
from .native_cursor import NativeCursorFilter
from .pages.appearance import AppearancePage
from .pages.motion import MotionPage
from .pages.tests import TestPage
from .pages.preferences import PreferencesPage


class ToastWidget(QFrame):
    """Floating macOS-style acrylic toast notification with smooth fade and responsive positioning."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName('toastNotification')
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._fade_out)
        self.anim = None

        self.setStyleSheet('''
            QFrame#toastNotification {
                background-color: rgba(36, 36, 38, 0.96);
                border: 0.5px solid rgba(255, 255, 255, 0.16);
                border-radius: 12px;
                padding: 8px 16px;
            }
            QLabel {
                color: #f5f5f7;
                font-weight: 500;
                font-size: 12.5px;
                background: transparent;
            }
        ''')
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 8)
        layout.setSpacing(8)

        self.icon_lbl = QLabel('✓')
        self.icon_lbl.setStyleSheet('color: #34c759; font-size: 13px; font-weight: bold;')
        layout.addWidget(self.icon_lbl)

        self.label = QLabel('')
        self.label.setWordWrap(True)
        layout.addWidget(self.label)

        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        self.hide()

    def show_message(self, message, is_error=False):
        if self.anim and self.anim.state() == QPropertyAnimation.State.Running:
            self.anim.stop()
        self.timer.stop()

        self.label.setText(message)
        if is_error:
            self.icon_lbl.setText('⚠️')
            self.icon_lbl.setStyleSheet('color: #ff453a; font-size: 13px;')
            self.setStyleSheet('''
                QFrame#toastNotification {
                    background-color: rgba(58, 20, 20, 0.96);
                    border: 0.5px solid rgba(255, 69, 58, 0.4);
                    border-radius: 12px;
                    padding: 8px 16px;
                }
                QLabel { color: #f5f5f7; font-size: 12.5px; background: transparent; }
            ''')
        else:
            self.icon_lbl.setText('✓')
            self.icon_lbl.setStyleSheet('color: #34c759; font-size: 13px; font-weight: bold;')
            self.setStyleSheet('''
                QFrame#toastNotification {
                    background-color: rgba(36, 36, 38, 0.96);
                    border: 0.5px solid rgba(255, 255, 255, 0.16);
                    border-radius: 12px;
                    padding: 8px 16px;
                }
                QLabel { color: #f5f5f7; font-size: 12.5px; background: transparent; }
            ''')

        if self.parent():
            self.adjustSize()
            pw = self.parent().width()
            ph = self.parent().height()
            w = min(max(260, self.sizeHint().width() + 32), max(60, pw - 40))
            h = max(42, self.sizeHint().height())
            cx = max(10, (pw - w) // 2)
            cy = max(10, ph - h - 80)
            self.setGeometry(cx, cy, w, h)

        self.opacity_effect.setOpacity(1.0)
        self.show()
        self.raise_()
        self.timer.start(2800)

    def _fade_out(self):
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(350)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.finished.connect(self.hide)
        self.anim.start()


class MainWindow(QMainWindow):
    """Revolutionary Modern Studio Window with Integrated Header & Floating Capsule Navigation."""
    def __init__(self, application):
        super().__init__()
        initialize_fonts()
        self.application = application
        self.busy = False
        self._threads = []
        self.load_error = None
        self._replace_draft = False
        try:
            self.applied = application.settings()
        except Exception as error:
            self.applied = CursorSettings()
            self.load_error = str(error)
        self._draft = self.applied
        self.setWindowTitle('Pointer · 光标工作台')

        # Load window and app icon
        self.icon_path = None
        for candidate in (
            ROOT / 'pointer.ico',
            ROOT / 'packaging' / 'windows' / 'pointer.ico',
            INSTALL_ROOT / 'pointer.ico',
            ROOT / 'assets' / 'pointer.png',
        ):
            if candidate.exists():
                self.icon_path = candidate
                break
        if self.icon_path:
            self.setWindowIcon(QIcon(str(self.icon_path)))

        self.resize(1180, 800)
        self.setMinimumSize(880, 620)
        self.setStyleSheet(STYLE)

        root = QWidget()
        root.setObjectName('rootWidget')
        self.setCentralWidget(root)
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ======================================================================
        # Top Header Bar: Integrated Branding, Floating Capsule Nav, Live Telemetry
        # ======================================================================
        top_header = QFrame()
        top_header.setObjectName('topHeader')
        header_layout = QHBoxLayout(top_header)
        header_layout.setContentsMargins(20, 12, 20, 12)
        header_layout.setSpacing(16)

        # 1. Left Branding Cluster
        brand_cluster = QHBoxLayout()
        brand_cluster.setSpacing(10)
        if self.icon_path:
            logo_lbl = QLabel()
            logo_pix = QPixmap(str(self.icon_path)).scaled(26, 26, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            logo_lbl.setPixmap(logo_pix)
            brand_cluster.addWidget(logo_lbl)

        brand_title = QLabel('Pointer')
        brand_title.setObjectName('brandTitle')
        brand_cluster.addWidget(brand_title)

        badge_lbl = QLabel('STUDIO')
        badge_lbl.setObjectName('brandBadge')
        brand_cluster.addWidget(badge_lbl)
        header_layout.addLayout(brand_cluster)

        header_layout.addStretch(1)

        # 2. Center macOS Segmented Control Navigation
        nav_capsule = QFrame()
        nav_capsule.setObjectName('navCapsule')
        capsule_layout = QHBoxLayout(nav_capsule)
        capsule_layout.setContentsMargins(3, 2, 3, 2)
        capsule_layout.setSpacing(2)

        self.navigation = []
        nav_items = [
            ('光标外观', 0),
            ('点击动效', 1),
            ('全景沙盒', 2),
            ('系统偏好', 3),
        ]
        for title, index in nav_items:
            button = QPushButton(title)
            button.setCheckable(True)
            button.setObjectName(f'nav{index}')
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, idx=index: self.select_page(idx))
            capsule_layout.addWidget(button)
            self.navigation.append(button)

        header_layout.addWidget(nav_capsule)

        header_layout.addStretch(1)

        # 3. Right Status & Quick Action Hub
        right_hub = QHBoxLayout()
        right_hub.setSpacing(10)

        status_chip = QFrame()
        status_chip.setObjectName('headerStatusChip')
        chip_layout = QHBoxLayout(status_chip)
        chip_layout.setContentsMargins(10, 4, 10, 4)
        chip_layout.setSpacing(6)

        self.status = QLabel('●  等待应用')
        self.status.setStyleSheet('color: #34c759; font-weight: 600; font-size: 11.5px;')
        chip_layout.addWidget(self.status)
        right_hub.addWidget(status_chip)

        version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip() if (ROOT / 'VERSION').exists() else '开发版'
        ver_lbl = QLabel(f'v{version}')
        ver_lbl.setObjectName('headerVersion')
        right_hub.addWidget(ver_lbl)

        header_layout.addLayout(right_hub)
        root_layout.addWidget(top_header)

        # ======================================================================
        # Content Workspace Area (Full Width Canvas)
        # ======================================================================
        content = QWidget()
        content.setObjectName('content')
        self.content_widget = content
        layout = QVBoxLayout(content)
        layout.setContentsMargins(24, 16, 24, 16)
        layout.setSpacing(12)

        # Banner Info Card
        banner = QFrame()
        banner.setObjectName('bannerBar')
        banner_layout = QHBoxLayout(banner)
        banner_layout.setContentsMargins(4, 4, 4, 4)
        banner_layout.setSpacing(12)

        info_box = QVBoxLayout()
        info_box.setSpacing(3)
        self.title = QLabel()
        self.title.setObjectName('pageTitle')
        info_box.addWidget(self.title)

        self.subtitle = QLabel()
        self.subtitle.setObjectName('subtitle')
        self.subtitle.setWordWrap(True)
        info_box.addWidget(self.subtitle)
        banner_layout.addLayout(info_box, 1)

        layout.addWidget(banner)

        # Central Stage: Stacked Pages & Grand Preview Showcase
        body = QHBoxLayout()
        body.setSpacing(18)

        self.stack = QStackedWidget()
        self.pages = [
            AppearancePage(self.change),
            MotionPage(self.change),
            TestPage(application),
            PreferencesPage(self)
        ]
        for page in self.pages:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.viewport().setAutoFillBackground(False)
            scroll.setWidget(page)
            page.setAutoFillBackground(False)
            self.stack.addWidget(scroll)
        body.addWidget(self.stack, 3)

        self.preview = PreviewPanel(self._draft)
        self.preview.setMinimumWidth(260)
        self.preview.setMaximumWidth(340)
        body.addWidget(self.preview, 2)
        layout.addLayout(body, 1)

        # Floating Toast Notification
        self.toast = ToastWidget(content)

        # ======================================================================
        # Floating Bottom Control Island
        # ======================================================================
        control_bar = QFrame()
        control_bar.setObjectName('controlBar')
        control_layout = QHBoxLayout(control_bar)
        control_layout.setContentsMargins(18, 8, 18, 8)
        control_layout.setSpacing(14)

        self.draft_label = QLabel('● 当前配置已同步')
        self.draft_label.setStyleSheet('color: #34c759; font-weight: 600;')
        control_layout.addWidget(self.draft_label)

        self.feedback = QLabel('所见即所得：配置在展台实时预览，应用后立即同步至 Windows 系统。')
        self.feedback.setObjectName('feedback')
        self.feedback.setWordWrap(True)
        control_layout.addWidget(self.feedback, 1)

        self.discard = QPushButton('放弃修改')
        self.discard.setCursor(Qt.CursorShape.PointingHandCursor)
        self.discard.clicked.connect(self.discard_changes)
        control_layout.addWidget(self.discard)

        self.apply_button = QPushButton('应用配置')
        self.apply_button.setObjectName('applyButton')
        self.apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_button.clicked.connect(self.apply_draft)
        control_layout.addWidget(self.apply_button)

        layout.addWidget(control_bar)
        root_layout.addWidget(content, 1)

        self.select_page(0)
        self.sync()

        if self.load_error:
            self.feedback.setText('配置无法读取：' + self.load_error + '。原文件已保留；请修复文件或明确选择默认配置。')
            self.apply_button.setEnabled(False)

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(1000)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start()
        self.refresh_status()

        self._last_prewarmed_draft = None
        self._prewarm_timer = QTimer(self)
        self._prewarm_timer.setSingleShot(True)
        self._prewarm_timer.setInterval(250)
        self._prewarm_timer.timeout.connect(self._trigger_prewarm)
        self._schedule_prewarm()

    def _schedule_prewarm(self):
        if hasattr(self, '_prewarm_timer'):
            self._prewarm_timer.start(250)

    def _trigger_prewarm(self):
        if getattr(self, 'busy', False) or not hasattr(self, 'application') or not hasattr(self.application, 'prewarm'):
            return
        draft = self._draft
        if getattr(self, '_last_prewarmed_draft', None) == draft:
            return
        self._last_prewarmed_draft = draft
        import threading
        thread = threading.Thread(target=self._run_prewarm, args=(draft,), daemon=True)
        thread.start()

    def _run_prewarm(self, draft):
        try:
            self.application.prewarm(draft)
        except Exception:
            pass

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'toast') and hasattr(self, 'content_widget'):
            pw = self.content_widget.width()
            ph = self.content_widget.height()
            w = min(max(260, self.toast.width()), max(60, pw - 40))
            h = max(42, self.toast.height())
            cx = max(10, (pw - w) // 2)
            cy = max(10, ph - h - 80)
            self.toast.setGeometry(cx, cy, w, h)

    def draft(self):
        return self._draft

    def set_draft(self, settings):
        self._draft = CursorSettings.from_dict(settings.to_dict())
        self.sync()
        self._schedule_prewarm()

    def request_apply(self):
        self.apply_draft()

    def change(self, **fields):
        if not hasattr(self, 'preview'):
            return
        self._draft = replace(self._draft, **fields)
        self.sync()
        self._schedule_prewarm()

    def sync(self):
        for index in (0, 1, 3):
            self.pages[index].sync(self._draft)
        self.preview.set_settings(self._draft)
        dirty = self._draft != self.applied
        if dirty:
            self.draft_label.setText('● 有未应用的修改')
            self.draft_label.setStyleSheet('color: #ff9f0a; font-weight: 600;')
        else:
            self.draft_label.setText('● 当前配置已同步')
            self.draft_label.setStyleSheet('color: #34c759; font-weight: 600;')
        self.discard.setEnabled(dirty and not self.busy)
        self.apply_button.setEnabled(not self.busy and not self.load_error)

    def select_page(self, index):
        titles = ['光标外观 · 视觉方案', '点击动效 · 触感微调', '全景沙盒 · 实操检验', '系统偏好 · 常驻自愈']
        descriptions = [
            '自适应圆角光标，智能感应背景亮度，在浅色与深色背景下始终保持清晰锐利。',
            '鼠标左键按下时给予富有生命力的微物理形变，松开后自然丝滑回正。',
            '在此实时观察 Windows 系统原生光标效果，支持全部 17 种指针与真实环境检验。',
            '管理后台常驻服务、开机启动自愈与个性化配置备份。'
        ]
        self.title.setText(titles[index])
        self.subtitle.setText(descriptions[index])
        self.stack.setCurrentIndex(index)
        for number, button in enumerate(self.navigation):
            button.setChecked(number == index)
        self.preview.setVisible(index in (0, 1))
        if index != 2:
            self.pages[2].set_wait(False)
            self.pages[2].button_release()

    def discard_changes(self):
        self._draft = self.applied
        self.sync()
        self.toast.show_message('已放弃未应用的草稿修改')
        self._schedule_prewarm()

    def apply_draft(self):
        desired = self._draft
        self.run_operation(lambda: self.application.apply(desired), '配置已成功应用至 Windows 系统', replace_draft=True)

    def run_operation(self, operation, success, replace_draft=False):
        if self.busy:
            return
        self.busy = True
        self.stack.setEnabled(False)
        self.sync()
        self.feedback.setText('正在处理，请稍候…')
        self._operation_message = success
        self._replace_draft = replace_draft
        thread = QThread(self)
        worker = Worker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self.operation_done)
        worker.failed.connect(self.operation_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self.release_thread)
        self._threads.append((thread, worker))
        thread.start()

    @Slot()
    def release_thread(self):
        thread = self.sender()
        self._threads = [pair for pair in self._threads if pair[0] is not thread]
        thread.deleteLater()

    @Slot(object)
    def operation_done(self, result):
        self.busy = False
        self.stack.setEnabled(True)
        if 'settings' in result:
            self.applied = CursorSettings.from_dict(result['settings'])
            if self._replace_draft:
                self._draft = self.applied
        elif 'startup_enabled' in result:
            self.applied = replace(self.applied, startup=result['startup_enabled'])
            self._draft = replace(self._draft, startup=result['startup_enabled'])
        self.feedback.setText(self._operation_message)
        self.toast.show_message(self._operation_message)
        self.sync()
        self.refresh_status()

    @Slot(str)
    def operation_failed(self, error):
        self.busy = False
        self.stack.setEnabled(True)
        err_msg = '未完成：' + error + '。请检查后重试。'
        self.feedback.setText(err_msg)
        self.toast.show_message(err_msg, is_error=True)
        self.sync()

    def refresh_status(self):
        if self.busy:
            return
        try:
            state = self.application.backend.snapshot()
            if state['running']:
                self.status.setText('●  光标效果运行中')
                self.status.setStyleSheet('color: #34c759; font-weight: 600; font-size: 11.5px;')
            else:
                self.status.setText('○  光标效果已暂停')
                self.status.setStyleSheet('color: #86868b; font-weight: 500; font-size: 11.5px;')
            if state.get('last_error'):
                self.feedback.setText('后台错误：' + state['last_error'])
        except Exception:
            self.status.setText('状态读取失败')
            self.status.setStyleSheet('color: #ff453a; font-weight: 500; font-size: 11.5px;')

    def reset_defaults(self):
        if self.load_error and QMessageBox.question(self, '重置配置', '现有配置无法读取。保留原文件副本并使用默认配置？') != QMessageBox.StandardButton.Yes:
            return
        if self.load_error:
            import time
            path = self.application.store.path
            if path.exists():
                path.replace(path.with_name(f'settings.invalid-{time.time_ns()}.json'))
            self.load_error = None
        self._draft = replace(CursorSettings(), startup=self.applied.startup)
        self.sync()
        self.toast.show_message('已恢复默认配置')

    def import_settings(self):
        path, _ = QFileDialog.getOpenFileName(self, '导入配置', '', 'JSON (*.json)')
        if path:
            try:
                self._draft = self.application.store.import_file(path)
                self.sync()
                self.feedback.setText('配置已导入草稿，点击“应用配置”后生效。')
                self.toast.show_message('配置已导入草稿，点击“应用配置”后生效')
            except Exception as error:
                err_text = '导入失败：' + str(error)
                self.feedback.setText(err_text)
                self.toast.show_message(err_text, is_error=True)

    def export_settings(self):
        path, _ = QFileDialog.getSaveFileName(self, '导出配置', 'Pointer-settings.json', 'JSON (*.json)')
        if path:
            try:
                self.application.store.export_file(path, self._draft)
                self.feedback.setText('配置已导出。')
                self.toast.show_message('配置已成功导出')
            except Exception as error:
                err_text = '导出失败：' + str(error)
                self.feedback.setText(err_text)
                self.toast.show_message(err_text, is_error=True)

    def confirm_restore(self):
        if QMessageBox.question(self, '恢复原光标', '恢复 Windows 原光标并关闭 Pointer 开机启动？') == QMessageBox.StandardButton.Yes:
            self.run_operation(self.application.restore, '原光标已恢复', replace_draft=True)

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
            self.feedback.setText('请等待当前操作完成后关闭窗口。')
            return
        if self._draft != self.applied and QMessageBox.question(self, '未应用的修改', '放弃未应用的修改并关闭窗口？') != QMessageBox.StandardButton.Yes:
            event.ignore()
            return
        event.accept()


def launch(test_page=False):
    from pointer.application import Application
    from pointer.windows.gui_ipc import WindowInstance, read_request, REPLY
    instance = WindowInstance()
    if not instance.primary:
        instance.close()
        return 0
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName('Pointer')
    app.setFont(QFont('Segoe UI Variable Text', 10))
    filter = NativeCursorFilter()
    app.installNativeEventFilter(filter)
    window = MainWindow(Application(DATA_ROOT, INSTALL_ROOT))
    if test_page:
        window.select_page(2)
    existing_request = read_request()
    handled = existing_request['token'] if existing_request else None

    def poll():
        nonlocal handled
        if instance.activation_requested():
            window.showNormal()
            window.raise_()
            window.activateWindow()
        try:
            request = read_request()
            if not request:
                return
            if request['token'] != handled:
                handled = request['token']
                detached = str(ROOT.resolve()).casefold() != str(request.get('target_root', ROOT)).casefold()
                ready = detached or (not window.busy and window.draft() == window.applied)
                _write_json(REPLY, {'token': handled, 'ready': ready, 'detached': detached, 'error': '请先应用或放弃未应用的修改，并关闭设置窗口。'})
                if ready and not detached:
                    window.close()
                elif not ready:
                    window.feedback.setText('升级等待中：请先完成当前操作或处理未应用的修改。')
                    window.showNormal()
                    window.activateWindow()
        except (OSError, ValueError, KeyError):
            pass

    timer = QTimer()
    timer.setInterval(250)
    timer.timeout.connect(poll)
    timer.start()
    window.show()
    try:
        return app.exec()
    finally:
        instance.close()
