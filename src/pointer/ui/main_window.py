"""Modern Fluent Obsidian Studio MainWindow for Pointer."""
from dataclasses import replace
import json
import sys
import threading
from PySide6.QtCore import Qt, QThread, QTimer, Slot, Signal, QPropertyAnimation, QEasingCurve, QEvent, QSize
from PySide6.QtGui import QFont, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QStackedWidget, QScrollArea, QFileDialog, QMessageBox,
    QGraphicsOpacityEffect, QStyle, QSizePolicy
)
from pointer.cursor.settings import CursorSettings, _write_json
from pointer.paths import DATA_ROOT, INSTALL_ROOT, ROOT
from .theme import STYLE, initialize_fonts
from .confirmations import ask_confirmation
from .workers import Worker
from .native_cursor import NativeCursorFilter
from .pages.motion import MotionPage
from .pages.tests import TestPage
from .pages.preferences import PreferencesPage
from .family_workspace import FamilyAppearancePage, FamilyPreviewPanel, workspace_style, navigation_icon
from .input_controls import PropertyScrollArea
from .colors import theme_colors


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
        if getattr(self.window(), 'reduce_motion', True):
            self.hide()
            return
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setDuration(140)
        self.anim.setStartValue(1.0)
        self.anim.setEndValue(0.0)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.finished.connect(self.hide)
        self.anim.start()


class MainWindow(QMainWindow):
    """Revolutionary Modern Studio Window with Integrated Header & Floating Capsule Navigation."""
    prewarm_finished = Signal()

    def __init__(self, application):
        super().__init__()
        initialize_fonts()
        self.application = application
        self.busy = False
        self.reduce_motion = not bool(QApplication.style().styleHint(QStyle.StyleHint.SH_Widget_Animate))
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
            icon = QIcon(str(self.icon_path))
            self.setWindowIcon(icon)
            QApplication.instance().setWindowIcon(icon)

        self.resize(1180, 800)
        self.setMinimumSize(880, 620)
        self.ui_dark = False
        self.setStyleSheet(STYLE + workspace_style())

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
            logo_pix = QIcon(str(self.icon_path)).pixmap(QSize(32, 32), self.devicePixelRatioF())
            logo_lbl.setPixmap(logo_pix)
            brand_cluster.addWidget(logo_lbl)

        brand_title = QLabel('Pointer')
        brand_title.setObjectName('brandTitle')
        brand_cluster.addWidget(brand_title)

        badge_lbl = QLabel('STUDIO')
        badge_lbl.setObjectName('brandBadge')
        brand_cluster.addWidget(badge_lbl)
        header_layout.addLayout(brand_cluster)

        header_layout.addSpacing(20)

        # 2. Center macOS Segmented Control Navigation
        nav_capsule = QFrame()
        nav_capsule.setObjectName('navCapsule')
        capsule_layout = QVBoxLayout(nav_capsule)
        capsule_layout.setContentsMargins(6, 12, 6, 12)
        capsule_layout.setSpacing(6)

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
            button.setFixedHeight(48)
            button.setMinimumWidth(88)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setIcon(navigation_icon(index, self.ui_dark, self.devicePixelRatioF()))
            button.setIconSize(QSize(20, 20))
            button.setAccessibleName(('外观', '动效', '测试', '设置')[index])
            button.clicked.connect(lambda checked=False, idx=index: self.select_page(idx))
            capsule_layout.addWidget(button)
            self.navigation.append(button)

        nav_capsule.setFixedWidth(112)
        self.nav_rail = nav_capsule
        capsule_layout.addStretch(1)

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
        self.status.setStyleSheet('color: ' + ('#b2b5c0' if self.ui_dark else '#5d5f68') + '; font-weight: 600; font-size: 12px;')
        chip_layout.addWidget(self.status)
        right_hub.addWidget(status_chip)

        version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip() if (ROOT / 'VERSION').exists() else '开发版'
        ver_lbl = QLabel(f'v{version}')
        ver_lbl.setObjectName('headerVersion')
        ver_lbl.hide()

        header_layout.addLayout(right_hub)
        self.theme_button = QPushButton('切换深色')
        self.theme_button.setObjectName('themeToggle')
        self.theme_button.setFixedHeight(36)
        self.theme_button.setAccessibleName('切换界面明暗，不改变光标配置')
        self.theme_button.clicked.connect(self.toggle_workspace_theme)
        self.theme_button.setToolTip('仅切换界面主题，不修改光标配置')
        badge_lbl.hide()
        for button, text in zip(self.navigation, ('外观', '动效', '测试', '设置')):
            button.setText(text)
        root_layout.addWidget(top_header)

        # ======================================================================
        # Content Workspace Area (Full Width Canvas)
        # ======================================================================
        content = QWidget()
        content.setObjectName('content')
        self.content_widget = content
        layout = QVBoxLayout(content)
        layout.setContentsMargins(16, 12, 16, 16)
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
        self.body_layout = body
        body.setSpacing(16)

        self.stack = QStackedWidget()
        self.pages = [
            FamilyAppearancePage(self.change),
            MotionPage(self.change),
            TestPage(application),
            PreferencesPage(self)
        ]
        self.pages[0].validation_changed.connect(self.sync)
        for page in self.pages:
            scroll = PropertyScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.viewport().setAutoFillBackground(False)
            scroll.setWidget(page)
            page.setAutoFillBackground(False)
            self.stack.addWidget(scroll)
        self.preview = FamilyPreviewPanel(self._draft)
        body.addWidget(self.preview, 3)
        body.addWidget(self.stack, 2)
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
        control_layout.setSpacing(8)

        self.draft_label = QLabel('● 当前配置已同步')
        self.draft_label.setStyleSheet('color: ' + ('#b2b5c0' if self.ui_dark else '#5d5f68') + '; font-weight: 600;')


        self.feedback = QLabel('预览不改变系统光标')
        self.feedback.setObjectName('feedback')
        self.feedback.setWordWrap(True)
        control_layout.addWidget(self.feedback, 1)
        control_layout.addWidget(self.draft_label)

        self.discard = QPushButton('放弃修改')
        self.discard.setCursor(Qt.CursorShape.PointingHandCursor)
        self.discard.clicked.connect(self.discard_changes)
        self.discard.setFixedWidth(88)
        control_layout.addWidget(self.discard)

        self.apply_button = QPushButton('应用配置')
        self.apply_button.setObjectName('applyButton')
        self.apply_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.apply_button.clicked.connect(self.apply_draft)
        self.apply_button.setText('应用更改')
        self.apply_button.setFixedWidth(112)
        control_layout.addWidget(self.apply_button)

        layout.addWidget(control_bar)
        workspace = QHBoxLayout()
        workspace.setContentsMargins(8, 0, 0, 0)
        workspace.setSpacing(0)
        workspace.addWidget(nav_capsule)
        workspace.addWidget(content, 1)
        root_layout.addLayout(workspace, 1)

        self.select_page(0)
        for widget in self.findChildren(QWidget):
            if widget.focusPolicy() != Qt.FocusPolicy.NoFocus:
                widget.setProperty('keyboardFocus', False)
                widget.installEventFilter(self)
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
        self._prewarm_running = False
        self._prewarm_attempted_draft = None
        self._prewarm_closing = False
        self._prewarm_lock = threading.Lock()
        self.prewarm_finished.connect(self._prewarm_done)
        self._prewarm_timer = QTimer(self)
        self._prewarm_timer.setSingleShot(True)
        self._prewarm_timer.setInterval(1000)
        self._prewarm_timer.timeout.connect(self._trigger_prewarm)
        self._schedule_prewarm()

        # System Tray Mini Island
        self.tray_controller = None
        if getattr(self.applied, 'tray_enabled', True):
            try:
                from .tray import TrayController
                self.tray_controller = TrayController(self)
            except Exception:
                self.tray_controller = None

        # Silent update check on startup
        if getattr(self.applied, 'auto_check_update', True):
            QTimer.singleShot(1500, self._check_update_silent_startup)

    def _schedule_prewarm(self, delay=None):
        if hasattr(self, '_prewarm_timer'):
            interval = 1000 if delay is None else delay
            self._prewarm_timer.start(interval)

    def _trigger_prewarm(self):
        if getattr(self, 'busy', False) or not hasattr(self, 'application') or not hasattr(self.application, 'prewarm'):
            return
        draft = self._draft
        if getattr(self, '_last_prewarmed_draft', None) == draft:
            return
        with self._prewarm_lock:
            if self._prewarm_running or self._prewarm_closing:
                return
            self._prewarm_running = True
            self._prewarm_attempted_draft = draft
        thread = threading.Thread(target=self._run_prewarm, args=(draft,), daemon=True)
        thread.start()

    def _run_prewarm(self, draft):
        try:
            if getattr(type(self.application), 'prewarm_isolated', None) is not None:
                self.application.prewarm_isolated(draft)
            else:
                self.application.prewarm(draft)
            if self._draft == draft:
                self._last_prewarmed_draft = draft
        except Exception:
            pass
        finally:
            with self._prewarm_lock:
                self._prewarm_running = False
            try:
                self.prewarm_finished.emit()
            except RuntimeError:
                pass  # The settings window may have been destroyed meanwhile.

    @Slot()
    def _prewarm_done(self):
        if not self._prewarm_closing and self._draft != self._prewarm_attempted_draft:
            self._schedule_prewarm()

    def start_preset_prewarm(self):
        # Build only the latest draft after input settles; speculative palettes
        # competed with previews and multiplied the resource renderer threads.
        self._schedule_prewarm()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'nav_rail'):
            self.nav_rail.setFixedWidth(112 if self.width() < 1000 else 152)
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

    def change(self, _immediate=False, **fields):
        if not hasattr(self, 'preview'):
            return
        self._draft = replace(self._draft, **fields)
        self.sync()
        self._schedule_prewarm()

    def sync(self):
        self.pages[0].setEnabled(not self.busy)
        for index in (0, 1, 3):
            self.pages[index].sync(self._draft)
        self.preview.set_settings(self._draft)
        dirty = self._draft != self.applied
        if dirty:
            self.draft_label.setText('未应用')
            self.draft_label.setStyleSheet('color: ' + ('#ffcf81' if self.ui_dark else '#9a4b00') + '; font-weight: 600;')
        else:
            self.draft_label.setText('无待应用更改')
            self.draft_label.setStyleSheet('color: ' + ('#b2b5c0' if self.ui_dark else '#5d5f68') + '; font-weight: 600;')
        self.discard.setEnabled(dirty and not self.busy)
        self.apply_button.setEnabled(dirty and not self.busy and not self.load_error and not self.pages[0].invalid_fields)
        self.apply_button.setText('处理中…' if self.busy else '应用更改')
        if getattr(self, 'tray_controller', None):
            try:
                self.tray_controller.update_menu()
            except Exception:
                pass

    def select_page(self, index):
        titles = ['外观', '动效', '光标测试', '应用设置']
        self.title.setText(titles[index])
        self.subtitle.setText('检查已应用的系统光标')
        self.subtitle.setVisible(index == 2)
        self.stack.setMinimumWidth(350 if index in (0, 1) else 0)
        self.stack.setMaximumWidth(500 if index in (0, 1) else 16777215)
        self.preview.clear_press()
        self.stack.setCurrentIndex(index)
        for number, button in enumerate(self.navigation):
            button.setChecked(number == index)
        self.preview.setVisible(index in (0, 1))
        if index != 2:
            self.pages[2].set_wait(False)
            self.pages[2].button_release()

    def toggle_workspace_theme(self):
        self.ui_dark = not self.ui_dark
        self.setStyleSheet(STYLE + workspace_style(self.ui_dark))
        for index, button in enumerate(self.navigation):
            button.setIcon(navigation_icon(index, self.ui_dark, self.devicePixelRatioF()))
        self.theme_button.setText('切换浅色' if self.ui_dark else '切换深色')
        self.theme_button.setAccessibleName(('当前深色界面，切换浅色' if self.ui_dark else '当前浅色界面，切换深色') + '，不改变光标配置')
        self.pages[2].set_theme(self.ui_dark)
        self.preview.ui_theme = 'dark' if self.ui_dark else 'light'
        self.pages[0].ui_theme = self.preview.ui_theme
        self.sync()
        self.refresh_status()

    def eventFilter(self, watched, event):
        if event.type() == QEvent.Type.FocusIn:
            keyboard = event.reason() in (Qt.FocusReason.TabFocusReason, Qt.FocusReason.BacktabFocusReason, Qt.FocusReason.ShortcutFocusReason)
            watched.setProperty('keyboardFocus', keyboard)
        elif event.type() == QEvent.Type.MouseButtonPress:
            watched.setProperty('keyboardFocus', False)
        else:
            return super().eventFilter(watched, event)
        watched.style().unpolish(watched)
        watched.style().polish(watched)
        watched.update()
        return super().eventFilter(watched, event)

    def event(self, event):
        if event.type() == QEvent.Type.WindowDeactivate and hasattr(self, 'preview'):
            self.preview.clear_press()
            self.pages[2].set_wait(False)
            self.pages[2].button_release()
        return super().event(event)

    def discard_changes(self):
        self.pages[0].reset_color_session()
        self._draft = self.applied
        self.feedback.setProperty('error', False)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        self.feedback.setText('已放弃未应用的更改')
        self.sync()
        self.toast.show_message('已放弃未应用的草稿修改')
        self._schedule_prewarm()

    def apply_draft(self):
        if self.busy or self._draft == self.applied or self.pages[0].invalid_fields:
            return
        desired = self._draft
        self.run_operation(lambda: self.application.apply(desired), '配置已应用，光标效果已启动', replace_draft=True)

    def run_operation(self, operation, success, replace_draft=False):
        if self.busy:
            return
        self.feedback.setProperty('error', False)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
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
        self.feedback.setProperty('error', False)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        if 'settings' in result:
            self.applied = CursorSettings.from_dict(result['settings'])
            if self._replace_draft:
                self._draft = self.applied
                self.pages[0].reset_color_session()
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
        err_msg = '未完成：' + error + '。可修正后重试。'
        self.feedback.setProperty('error', True)
        self.feedback.style().unpolish(self.feedback)
        self.feedback.style().polish(self.feedback)
        self.feedback.setText(err_msg)
        self.toast.show_message(err_msg, is_error=True)
        self.sync()

    def refresh_status(self):
        if self.busy:
            return
        try:
            state = self.application.runtime_status()
            if state.get('last_error'):
                message = '光标后台异常'
            elif state.get('starting'):
                message = '光标效果启动中'
            elif state.get('effects_paused') and state.get('pause_reason') == 'fullscreen':
                message = '全屏免打扰 · 暂停动效'
            elif state.get('running'):
                message = '光标效果运行中'
            else:
                message = '光标效果已暂停 · 可在设置中恢复'
            self.status.setText(message)
            colors = theme_colors(self.ui_dark)
            style = 'color: ' + colors['muted'] + '; font-weight: 500; font-size: 12px;'
            if self.status.styleSheet() != style:
                self.status.setStyleSheet(style)
            if state.get('last_error'):
                self.feedback.setText('后台错误：' + state['last_error'])
        except Exception:
            self.status.setText('状态读取失败')
            self.status.setStyleSheet('color: #ff453a; font-weight: 500; font-size: 11.5px;')

    def reset_defaults(self):
        if self.load_error and ask_confirmation(self, '重置配置', '现有配置无法读取。保留原文件副本并使用默认配置？', '使用默认配置', '取消') != QMessageBox.StandardButton.Yes:
            return
        if self.load_error:
            import time
            path = self.application.store.path
            if path.exists():
                path.replace(path.with_name(f'settings.invalid-{time.time_ns()}.json'))
            self.load_error = None
        self._draft = replace(CursorSettings(), **{name: getattr(self._draft, name) for name in
            ('startup', 'tray_enabled', 'auto_check_update', 'skip_update_version')})
        self.sync()
        self.feedback.setText('默认参数已载入草稿，点击“应用更改”后生效。')
        self.toast.show_message('默认参数已载入草稿')
        self._schedule_prewarm()

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

    def import_theme_package(self):
        path, _ = QFileDialog.getOpenFileName(self, '导入主题包', '', 'Pointer 主题包 (*.pointertheme *.json);;所有文件 (*.*)')
        if path:
            try:
                settings, meta = self.application.store.import_theme(path)
                self._draft = settings
                self.sync()
                name = meta.get('name', '未命名主题')
                msg = f'已载入主题包「{name}」，点击“应用配置”后生效。'
                self.feedback.setText(msg)
                self.toast.show_message(msg)
            except Exception as error:
                err_text = '主题包导入失败：' + str(error)
                self.feedback.setText(err_text)
                self.toast.show_message(err_text, is_error=True)

    def export_theme_package(self):
        path, _ = QFileDialog.getSaveFileName(self, '导出主题包', 'CustomTheme.pointertheme', 'Pointer 主题包 (*.pointertheme);;所有文件 (*.*)')
        if path:
            try:
                self.application.store.export_theme(path, self._draft, name="Custom Theme", author="User", desc="由 Pointer Studio 导出的个性化主题")
                self.feedback.setText('主题包已成功导出。')
                self.toast.show_message('主题包已成功导出')
            except Exception as error:
                err_text = '主题包导出失败：' + str(error)
                self.feedback.setText(err_text)
                self.toast.show_message(err_text, is_error=True)

    def current_version(self):
        v_file = ROOT / 'VERSION'
        return v_file.read_text(encoding='utf-8').strip() if v_file.exists() else '1.3.0-beta.1'

    def _check_update_silent_startup(self):
        if self.isVisible():
            self._update_checker().start(self.current_version())

    def _update_checker(self):
        if not hasattr(self, '_update_check'):
            from .update_dialog import UpdateCheck
            self._update_check = UpdateCheck(self)
            self._update_check.completed.connect(self._update_check_completed)
            self._update_check.cancelled.connect(self._update_check_cancelled)
            label = self.pages[3].update_status_lbl
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setWordWrap(True)
            label.setMinimumWidth(120)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        return self._update_check

    def check_updates_interactive(self):
        if not self.isVisible():
            return
        pref_page = self.pages[3]
        if hasattr(pref_page, 'update_status_lbl'):
            pref_page.update_status_lbl.setText('正在检查更新…')
            pref_page.update_status_lbl.setToolTip('')
            pref_page.update_status_lbl.setStyleSheet('color: #007aff; font-size: 12px;')
        if hasattr(pref_page, 'check_update_btn'):
            pref_page.check_update_btn.setEnabled(False)

        self._update_checker().start(self.current_version(), interactive=True)

    @Slot(bool)
    def _update_check_cancelled(self, interactive):
        if interactive:
            pref_page = self.pages[3]
            pref_page.check_update_btn.setEnabled(True)
            pref_page.update_status_lbl.setText('检查已取消。')
            pref_page.update_status_lbl.setStyleSheet('font-size: 12px;')

    @Slot(object, str, bool)
    def _update_check_completed(self, info, error, interactive):
        if interactive:
            pref_page = self.pages[3]
            pref_page.check_update_btn.setEnabled(True)
        if not self.isVisible():
            return
        if error:
            if interactive:
                label = pref_page.update_status_lbl
                message = f'检查失败：{error}'
                label.setStyleSheet('color: #ff453a; font-size: 12px;')
                label.setToolTip(message)
                label.setText(label.fontMetrics().elidedText(message, Qt.TextElideMode.ElideRight,
                                                            max(120, min(480, label.width() - 8))))
                self.toast.show_message('检查更新失败，请查看版本区的说明。', is_error=True)
            return
        if info.get('available'):
            if interactive:
                pref_page.update_status_lbl.setText(f"发现新版本 v{info.get('latest_version')}")
                pref_page.update_status_lbl.setStyleSheet('color: #34c759; font-size: 12px;')
            if interactive or info.get('latest_version') != getattr(self.applied, 'skip_update_version', ''):
                self._show_update_dialog(info)
        elif interactive:
            message = f'当前已是最新版本 (v{self.current_version()})'
            pref_page.update_status_lbl.setText(message)
            pref_page.update_status_lbl.setStyleSheet('color: #34c759; font-size: 12px;')
            self.toast.show_message(message)

    def _show_update_dialog(self, info):
        if not self.isVisible() or QApplication.activeModalWidget() is not None:
            return
        from .update_dialog import UpdateDialog
        dialog = UpdateDialog(info, self.application, self)
        dialog.exec()
        dialog.deleteLater()

    def confirm_restore(self):
        if ask_confirmation(self, '恢复原光标', '恢复 Windows 原光标并关闭 Pointer 开机启动？', '恢复原光标', '取消') == QMessageBox.StandardButton.Yes:
            self.run_operation(self.application.restore, '原光标已恢复', replace_draft=True)

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
            self.feedback.setText('请等待当前操作完成后关闭窗口。')
            return
        if self._draft != self.applied and ask_confirmation(self, '未应用的修改', '放弃未应用的修改并关闭窗口？', '放弃修改', '继续编辑') != QMessageBox.StandardButton.Yes:
            event.ignore()
            return
        self._prewarm_closing = True
        self._prewarm_timer.stop()
        event.accept()


def _ready_for_upgrade(window):
    return not window.busy and window.draft() == window.applied and not getattr(window, 'sidebar_dirty', False)


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
    # Imported here because MaterialWindow's inheritance chain uses MainWindow.
    from .material_workspace import MaterialWindow
    from .sidebar_settings import SidebarStore
    helper, composition_error = None, None
    if sys.platform == 'win32' and app.platformName() == 'windows':
        from pointer.windows.composition_host import prepare_helper
        try:
            helper = prepare_helper(DATA_ROOT / 'composition-cache')
        except OSError as error:
            composition_error = str(error)
    window = MaterialWindow(Application(DATA_ROOT, INSTALL_ROOT),
                            sidebar_store=SidebarStore(DATA_ROOT / 'sidebar-appearance.json'),
                            composition_helper=helper, composition_error=composition_error)
    window.start_preset_prewarm()
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
                ready = detached or _ready_for_upgrade(window)
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
        try:
            host = getattr(window, '_backdrop_host', None)
            if host is not None:
                host.shutdown()
        finally:
            instance.close()
