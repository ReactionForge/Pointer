"""Own the editable draft; Windows changes go through Application workers."""
from dataclasses import replace
import json
import sys
from PySide6.QtCore import Qt, QThread, QTimer, Slot
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QStackedWidget, QScrollArea, QFileDialog, QMessageBox
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


class MainWindow(QMainWindow):
    def __init__(self, application):
        super().__init__()
        initialize_fonts()
        self.application = application
        self.busy = False
        self._threads = []
        self.load_error = None
        try:
            self.applied = application.settings()
        except Exception as error:
            self.applied = CursorSettings()
            self.load_error = str(error)
        self._draft = self.applied
        self.setWindowTitle('Pointer · 光标设置')
        icon = ROOT/'pointer.ico'
        if not icon.exists():
            icon = ROOT/'packaging/windows/pointer.ico'
        self.setWindowIcon(QIcon(str(icon)))
        self.resize(1100,760)
        self.setMinimumSize(900,700)
        self.setStyleSheet(STYLE)
        root = QWidget()
        self.setCentralWidget(root)
        horizontal = QHBoxLayout(root)
        horizontal.setContentsMargins(0,0,0,0)
        horizontal.setSpacing(0)
        sidebar = QFrame()
        sidebar.setObjectName('sidebar')
        sidebar.setFixedWidth(198)
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(20,30,20,24)
        brand = QLabel('Pointer')
        brand.setObjectName('brand')
        side.addWidget(brand)
        side.addWidget(QLabel('让每一次指向更清晰'))
        side.addSpacing(32)
        self.navigation = []
        for index,title in enumerate(['光标外观','左键动效','光标测试','应用设置']):
            button = QPushButton(title)
            button.setCheckable(True)
            button.setObjectName('nav'+str(index))
            button.clicked.connect(lambda checked=False,index=index:self.select_page(index))
            side.addWidget(button)
            self.navigation.append(button)
        side.addStretch()
        self.status = QLabel('●  等待应用')
        self.status.setWordWrap(True)
        side.addWidget(self.status)
        version = (ROOT / 'VERSION').read_text(encoding='utf-8').strip() if (ROOT/'VERSION').exists() else '开发版'
        side.addWidget(QLabel('v'+version))
        horizontal.addWidget(sidebar)
        content = QWidget()
        content.setObjectName('content')
        layout = QVBoxLayout(content)
        layout.setContentsMargins(30,28,30,20)
        layout.setSpacing(16)
        self.title = QLabel()
        self.title.setObjectName('pageTitle')
        layout.addWidget(self.title)
        self.subtitle = QLabel()
        self.subtitle.setObjectName('subtitle')
        self.subtitle.setWordWrap(True)
        layout.addWidget(self.subtitle)
        body = QHBoxLayout()
        body.setSpacing(22)
        self.stack = QStackedWidget()
        self.pages = [AppearancePage(self.change),MotionPage(self.change),TestPage(application),PreferencesPage(self)]
        for page in self.pages:
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setWidget(page)
            self.stack.addWidget(scroll)
        body.addWidget(self.stack,3)
        self.preview = PreviewPanel(self._draft)
        self.preview.setMinimumWidth(250)
        self.preview.setMaximumWidth(320)
        body.addWidget(self.preview,2)
        layout.addLayout(body,1)
        self.feedback = QLabel('配置先在右侧预览，应用后启用系统光标。')
        self.feedback.setObjectName('feedback')
        self.feedback.setWordWrap(True)
        layout.addWidget(self.feedback)
        row = QHBoxLayout()
        self.draft_label = QLabel('当前配置')
        row.addWidget(self.draft_label)
        row.addStretch()
        self.discard = QPushButton('放弃修改')
        self.discard.clicked.connect(self.discard_changes)
        row.addWidget(self.discard)
        self.apply_button = QPushButton('应用配置')
        self.apply_button.setObjectName('applyButton')
        self.apply_button.clicked.connect(self.apply_draft)
        row.addWidget(self.apply_button)
        layout.addLayout(row)
        horizontal.addWidget(content,1)
        self.select_page(0)
        self.sync()
        if self.load_error:
            self.feedback.setText('配置无法读取：'+self.load_error+'。原文件已保留；请修复文件或明确选择默认配置。')
            self.apply_button.setEnabled(False)
        self.status_timer = QTimer(self)
        self.status_timer.setInterval(1000)
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start()
        self.refresh_status()

    def draft(self):
        return self._draft

    def change(self, **fields):
        if not hasattr(self,'preview'):
            return
        self._draft = replace(self._draft, **fields)
        self.sync()

    def sync(self):
        for index in (0,1,3):
            self.pages[index].sync(self._draft)
        self.preview.set_settings(self._draft)
        dirty = self._draft != self.applied
        self.draft_label.setText('有未应用的修改' if dirty else '当前配置')
        self.discard.setEnabled(dirty and not self.busy)
        self.apply_button.setEnabled(not self.busy and not self.load_error)

    def select_page(self,index):
        titles = ['光标外观','左键动效','光标测试','应用设置']
        descriptions = ['熟悉的圆角造型，在深浅背景下都清楚可见。','按下时给出轻巧反馈，松开后自然回正。','这里观察已应用的系统光标。修改草稿后，请先应用。','管理运行状态、开机启动和你的配置文件。']
        self.title.setText(titles[index])
        self.subtitle.setText(descriptions[index])
        self.stack.setCurrentIndex(index)
        for number,button in enumerate(self.navigation):
            button.setChecked(number==index)
        self.preview.setVisible(index in (0,1))
        if index != 2:
            self.pages[2].set_wait(False)
            self.pages[2].button_release()

    def discard_changes(self):
        self._draft = self.applied
        self.sync()

    def apply_draft(self):
        desired = self._draft
        self.run_operation(lambda:self.application.apply(desired),'配置已应用')

    def run_operation(self, operation, success):
        if self.busy:
            return
        self.busy = True
        self.stack.setEnabled(False)
        self.sync()
        self.feedback.setText('正在处理，请稍候…')
        self._operation_message = success
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
        self._threads.append((thread,worker))
        thread.start()

    @Slot()
    def release_thread(self):
        thread = self.sender()
        self._threads = [pair for pair in self._threads if pair[0] is not thread]
        thread.deleteLater()

    @Slot(object)
    def operation_done(self,result):
        self.busy = False
        self.stack.setEnabled(True)
        if 'settings' in result:
            self.applied = CursorSettings.from_dict(result['settings'])
            self._draft = self.applied
        elif 'startup_enabled' in result:
            self.applied = replace(self.applied,startup=result['startup_enabled'])
            self._draft = replace(self._draft,startup=result['startup_enabled'])
        self.feedback.setText(self._operation_message)
        self.sync()
        self.refresh_status()

    @Slot(str)
    def operation_failed(self,error):
        self.busy = False
        self.stack.setEnabled(True)
        self.feedback.setText('未完成：'+error+'。请检查后重试。')
        self.sync()

    def refresh_status(self):
        if self.busy:
            return
        try:
            state = self.application.backend.snapshot()
            self.status.setText('●  光标效果运行中' if state['running'] else '○  光标效果已暂停')
            if state.get('last_error'):
                self.feedback.setText('后台错误：'+state['last_error'])
        except Exception as error:
            self.status.setText('状态读取失败')

    def reset_defaults(self):
        if self.load_error and QMessageBox.question(self,'重置配置','现有配置无法读取。保留原文件副本并使用默认配置？') != QMessageBox.StandardButton.Yes:
            return
        if self.load_error:
            import time
            path = self.application.store.path
            if path.exists():
                path.replace(path.with_name(f'settings.invalid-{time.time_ns()}.json'))
            self.load_error = None
        self._draft = replace(CursorSettings(),startup=self.applied.startup)
        self.sync()

    def import_settings(self):
        path,_ = QFileDialog.getOpenFileName(self,'导入配置','','JSON (*.json)')
        if path:
            try:
                self._draft = self.application.store.import_file(path)
                self.sync()
                self.feedback.setText('配置已导入草稿，点击“应用配置”后生效。')
            except Exception as error:
                self.feedback.setText('导入失败：'+str(error))

    def export_settings(self):
        path,_ = QFileDialog.getSaveFileName(self,'导出配置','Pointer-settings.json','JSON (*.json)')
        if path:
            try:
                self.application.store.export_file(path,self._draft)
                self.feedback.setText('配置已导出。')
            except Exception as error:
                self.feedback.setText('导出失败：'+str(error))

    def confirm_restore(self):
        if QMessageBox.question(self,'恢复原光标','恢复 Windows 原光标并关闭 Pointer 开机启动？') == QMessageBox.StandardButton.Yes:
            self.run_operation(self.application.restore,'原光标已恢复')

    def closeEvent(self,event):
        if self.busy:
            event.ignore()
            self.feedback.setText('请等待当前操作完成后关闭窗口。')
            return
        if self._draft != self.applied and QMessageBox.question(self,'未应用的修改','放弃未应用的修改并关闭窗口？') != QMessageBox.StandardButton.Yes:
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
    app.setFont(QFont('Microsoft YaHei UI',10))
    filter = NativeCursorFilter()
    app.installNativeEventFilter(filter)
    window = MainWindow(Application(DATA_ROOT,INSTALL_ROOT))
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
                detached = str(ROOT.resolve()).casefold() != str(request.get('target_root',ROOT)).casefold()
                ready = detached or (not window.busy and window.draft() == window.applied)
                _write_json(REPLY,{'token':handled,'ready':ready,'detached':detached,'error':'请先应用或放弃未应用的修改，并关闭设置窗口。'})
                if ready and not detached:
                    window.close()
                elif not ready:
                    window.feedback.setText('升级等待中：请先完成当前操作或处理未应用的修改。')
                    window.showNormal()
                    window.activateWindow()
        except (OSError,ValueError,KeyError):
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
