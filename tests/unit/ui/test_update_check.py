"""Update checks return to the GUI thread and always release the checking state."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import threading
import time
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QThread, Qt, QEvent, QCoreApplication
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pointer.cursor.settings import CursorSettings
from pointer.ui.main_window import MainWindow
from pointer.ui.update_dialog import UpdateDialog
from shiboken6 import isValid


APP = QApplication.instance() or QApplication([])
INSTALL_INFO = {
    'latest_version': '9.0.0', 'current_version': '1.0.0',
    'download_url': 'https://invalid.example/Pointer-setup.exe',
    'asset_name': 'Pointer-setup.exe', 'asset_size': 8,
    'expected_sha256': 'a' * 64, 'can_auto_install': True,
    'html_url': 'https://invalid.example/releases',
}


def wait_until(predicate, timeout=600):
    deadline = time.monotonic() + timeout / 1000
    while not predicate() and time.monotonic() < deadline:
        QTest.qWait(5)
    return predicate()


class UpdateCheckTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.window = MainWindow(self.backend)
        self.addCleanup(self.release_window, self.window)
        self.window.status_timer.stop()
        self.window._prewarm_timer.stop()
        self.window.preview.timer.stop()
        self.window.toast.show_message = Mock()
        self.window._show_update_dialog = Mock()
        self.window.show()
        APP.processEvents()
        self.page = self.window.pages[3]

    def release_window(self, window):
        if isValid(window):
            deadline = time.monotonic() + 3
            while window._threads and time.monotonic() < deadline:
                QTest.qWait(10)
            self.assertEqual(window._threads, [], 'Native operation thread did not finish')
            window.discard_changes()
            self.assertTrue(window.close())
            window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def tearDown(self):
        self.release_window(self.window)
        APP.processEvents()
        for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
            getattr(self.backend, name).assert_not_called()

    def test_no_update_releases_button_and_reports_completion_on_gui_thread(self):
        callbacks = []
        self.window.toast.show_message.side_effect = lambda *args, **kwargs: callbacks.append(QThread.currentThread())
        with patch('pointer.updater.check_for_updates', return_value={'available': False}) as check:
            self.window.check_updates_interactive()
            self.assertTrue(wait_until(self.page.check_update_btn.isEnabled), 'Finished check left the button disabled')
        check.assert_called_once()
        self.assertIn('当前已是最新版本', self.page.update_status_lbl.text())
        self.assertEqual(callbacks, [APP.thread()])
        self.window._show_update_dialog.assert_not_called()

    def test_network_error_releases_button_and_keeps_exception_message(self):
        with patch('pointer.updater.check_for_updates', side_effect=TimeoutError('test network timeout')):
            self.window.check_updates_interactive()
            self.assertTrue(wait_until(self.page.check_update_btn.isEnabled), 'Failed check left the button disabled')
        self.assertIn('test network timeout', self.page.update_status_lbl.toolTip())
        self.window.toast.show_message.assert_called_once()
        self.window._show_update_dialog.assert_not_called()

    def test_available_update_opens_on_gui_thread_after_button_is_released(self):
        info = {'available': True, 'latest_version': '9.0.0'}
        callbacks = []
        self.window._show_update_dialog.side_effect = lambda result: callbacks.append(
            (QThread.currentThread(), self.page.check_update_btn.isEnabled(), result))
        with patch('pointer.updater.check_for_updates', return_value=info):
            self.window.check_updates_interactive()
            self.assertTrue(wait_until(lambda: bool(callbacks)), 'Available update was never delivered')
        self.assertEqual(callbacks, [(APP.thread(), True, info)])
        self.assertIn('9.0.0', self.page.update_status_lbl.text())

    def test_silent_startup_delivers_available_update_without_checking_ui(self):
        info = {'available': True, 'latest_version': '9.0.0'}
        with patch('pointer.updater.check_for_updates', return_value=info):
            self.window._check_update_silent_startup()
            self.assertTrue(wait_until(lambda: self.window._show_update_dialog.called))
        self.assertTrue(self.page.check_update_btn.isEnabled())
        self.window.toast.show_message.assert_not_called()

    def test_gui_deadline_releases_button_and_late_result_cannot_replace_retry(self):
        entered, release, returned = threading.Event(), threading.Event(), threading.Event()
        def delayed_check(*args, **kwargs):
            entered.set()
            release.wait(2)
            returned.set()
            return {'available': True, 'latest_version': '9.0.0'}
        try:
            with patch('pointer.updater.check_for_updates', side_effect=delayed_check), \
                    patch('pointer.ui.update_dialog.UPDATE_CHECK_TIMEOUT_MS', 30, create=True):
                self.window.check_updates_interactive()
                self.assertTrue(wait_until(entered.is_set))
                self.assertTrue(wait_until(self.page.check_update_btn.isEnabled), 'Deadline did not finish the check')
            self.assertIn('超时', self.page.update_status_lbl.text())
            with patch('pointer.updater.check_for_updates', return_value={'available': False}):
                self.window.check_updates_interactive()
                self.assertTrue(wait_until(self.page.check_update_btn.isEnabled))
            completed_status = self.page.update_status_lbl.text()
            release.set()
            self.assertTrue(wait_until(returned.is_set))
            QTest.qWait(30)
            self.assertEqual(self.page.update_status_lbl.text(), completed_status)
            self.window._show_update_dialog.assert_not_called()
        finally:
            release.set()

    def test_closing_window_discards_pending_result_without_touching_backend(self):
        entered, release, returned = threading.Event(), threading.Event(), threading.Event()
        def delayed_check(*args, **kwargs):
            entered.set()
            release.wait(2)
            returned.set()
            return {'available': True, 'latest_version': '9.0.0'}
        try:
            with patch('pointer.updater.check_for_updates', side_effect=delayed_check):
                self.window.check_updates_interactive()
                self.assertTrue(wait_until(entered.is_set))
                self.window.close()
                release.set()
                self.assertTrue(wait_until(returned.is_set))
                QTest.qWait(30)
            self.window._show_update_dialog.assert_not_called()
            self.window.toast.show_message.assert_not_called()
            self.window.show()
            APP.processEvents()
            self.assertTrue(self.page.check_update_btn.isEnabled())
        finally:
            release.set()

    def test_startup_and_manual_requests_share_one_check_and_manual_ignores_skip(self):
        entered, release = threading.Event(), threading.Event()
        def delayed_check(*args, **kwargs):
            entered.set()
            release.wait(2)
            return {'available': True, 'latest_version': '9.0.0'}
        from dataclasses import replace
        self.window.applied = replace(self.window.applied, skip_update_version='9.0.0')
        self.window._draft = self.window.applied
        try:
            with patch('pointer.updater.check_for_updates', side_effect=delayed_check) as check:
                self.window._check_update_silent_startup()
                self.assertTrue(wait_until(entered.is_set))
                self.window.check_updates_interactive()
                self.window.check_updates_interactive()
                release.set()
                self.assertTrue(wait_until(lambda: self.window._show_update_dialog.called))
                check.assert_called_once()
            self.assertTrue(self.page.check_update_btn.isEnabled())
        finally:
            release.set()

    def test_destroyed_window_disconnects_result_receiver(self):
        entered, release, returned = threading.Event(), threading.Event(), threading.Event()
        show_dialog = self.window._show_update_dialog
        def delayed_check(*args, **kwargs):
            entered.set()
            release.wait(2)
            returned.set()
            return {'available': True, 'latest_version': '9.0.0'}
        try:
            with patch('pointer.updater.check_for_updates', side_effect=delayed_check):
                self.window.check_updates_interactive()
                self.assertTrue(wait_until(entered.is_set))
                self.window.close()
                self.window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                self.assertFalse(isValid(self.window))
                release.set()
                self.assertTrue(wait_until(returned.is_set))
                QTest.qWait(30)
            show_dialog.assert_not_called()
        finally:
            release.set()

    def test_rejected_dirty_close_preserves_pending_check(self):
        entered, release = threading.Event(), threading.Event()
        def delayed_check(*args, **kwargs):
            entered.set()
            release.wait(2)
            return {'available': False}
        self.window.change(size=40 if self.window.applied.size != 40 else 48)
        try:
            with patch('pointer.updater.check_for_updates', side_effect=delayed_check):
                self.window.check_updates_interactive()
                self.assertTrue(wait_until(entered.is_set))
                from PySide6.QtWidgets import QMessageBox
                with patch('pointer.ui.main_window.ask_confirmation', return_value=QMessageBox.StandardButton.No):
                    self.assertFalse(self.window.close())
                self.assertTrue(self.window.isVisible())
                self.assertFalse(self.page.check_update_btn.isEnabled())
                release.set()
                self.assertTrue(wait_until(self.page.check_update_btn.isEnabled))
            self.assertIn('当前已是最新版本', self.page.update_status_lbl.text())
        finally:
            release.set()

    def test_long_network_detail_keeps_material_settings_and_retry_button_in_viewport(self):
        from pointer.ui.material_workspace import MaterialWindow
        self.release_window(self.window)
        self.window = MaterialWindow(self.backend)
        self.window.status_timer.stop()
        self.window._prewarm_timer.stop()
        self.window.preview.timer.stop()
        self.window._show_update_dialog = Mock()
        self.window.toast.show_message = Mock()
        self.window.resize(1180, 920)
        self.window.select_page(3)
        self.window.show()
        APP.processEvents()
        self.page = self.window.pages[3]
        detail = '连接失败：https://invalid.example/' + 'diagnostic_detail_' * 24
        with patch('pointer.updater.check_for_updates', side_effect=OSError(detail)):
            self.window.check_updates_interactive()
            self.assertTrue(wait_until(self.page.check_update_btn.isEnabled))
        for width in (1180, 880):
            self.window.resize(width, 920)
            APP.processEvents()
            scroll = self.window.stack.widget(3)
            self.assertLessEqual(scroll.widget().width(), scroll.viewport().width())
            self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
            scroll.ensureWidgetVisible(self.page.check_update_btn)
            APP.processEvents()
            self.assertTrue(scroll.viewport().rect().contains(
                self.page.check_update_btn.mapTo(scroll.viewport(), self.page.check_update_btn.rect().center())))
        self.assertIn(detail, self.page.update_status_lbl.toolTip())


class UpdateDialogCloseTests(unittest.TestCase):
    def tearDown(self):
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_incomplete_metadata_never_launches_or_downloads(self):
        for overrides in ({'expected_sha256': None}, {'asset_size': 0}, {'asset_size': None},
                          {'asset_size': True}, {'can_auto_install': False}, {'expected_sha256': 'bad'}):
            with self.subTest(overrides=overrides):
                dialog = UpdateDialog(dict(INSTALL_INFO, **overrides))
                with patch('pointer.ui.update_dialog.download_update_package') as download, \
                     patch('pointer.ui.update_dialog.trigger_silent_upgrade') as install, \
                     patch('pointer.ui.update_dialog.QDesktopServices.openUrl', return_value=True) as browser:
                    self.assertEqual(dialog.update_btn.text(), '手动下载')
                    dialog._start_download()
                    dialog._on_download_finished('unused installer')
                    download.assert_not_called()
                    install.assert_not_called()
                    browser.assert_called_once()
                dialog.close()
                dialog.deleteLater()

    def test_close_and_escape_cancel_without_waiting_or_starting_installer(self):
        for action in ('close', 'reject'):
            with self.subTest(action=action):
                entered, release = threading.Event(), threading.Event()
                cancel_flags = []
                def blocked_download(*args, **kwargs):
                    cancel_flags.append(kwargs['cancel_flag'])
                    entered.set()
                    release.wait(3)
                    # A completed read can race with cancellation; it must not install.
                    return 'fake checksum'
                from PySide6.QtWidgets import QWidget
                owner = QWidget()
                owner._ready_for_upgrade = Mock(return_value=True)
                owner._finish_upgrade = Mock()
                dialog = UpdateDialog(INSTALL_INFO, parent=owner)
                dialog.show()
                APP.processEvents()
                try:
                    with patch('pointer.ui.update_dialog.download_update_package', side_effect=blocked_download), \
                            patch('pointer.ui.update_dialog.trigger_silent_upgrade') as install, \
                            patch.object(APP, 'quit'):
                        dialog._start_download()
                        self.assertTrue(wait_until(entered.is_set))
                        started = time.monotonic()
                        if action == 'reject':
                            QTest.keyClick(dialog, Qt.Key.Key_Escape)
                        else:
                            dialog.close()
                        self.assertLess(time.monotonic() - started, 0.2, 'Closing must not join a network thread')
                        self.assertTrue(cancel_flags[0](), 'Dialog dismissal did not cancel the download')
                        release.set()
                        self.assertTrue(wait_until(lambda: not dialog.worker.isRunning()))
                        QTest.qWait(30)
                        install.assert_not_called()
                finally:
                    release.set()
                    with patch('pointer.ui.update_dialog.trigger_silent_upgrade'), patch.object(APP, 'quit'):
                        wait_until(lambda: not dialog.worker.isRunning(), timeout=1000)
                        dialog.close()
                        dialog.deleteLater()
                        owner.deleteLater()
                        APP.processEvents()


class UpdateHandoffTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from pointer.cursor.settings import SettingsStore
        self.temp = tempfile.TemporaryDirectory()
        self.backend = Mock()
        self.settings = CursorSettings(tray_enabled=False, auto_check_update=False, startup=True)
        self.backend.store = SettingsStore(Path(self.temp.name))
        self.backend.store.save(self.settings)
        self.backend.settings.side_effect = self.backend.store.load
        self.backend.runtime_status.return_value = {'running': True}
        self.window = MainWindow(self.backend)
        self.window.status_timer.stop()
        self.window._prewarm_timer.stop()
        self.window.preview.timer.stop()
        self.dialog = UpdateDialog(INSTALL_INFO, self.backend, self.window)

    def tearDown(self):
        self.dialog.reject()
        self.window.busy = False
        self.window._draft = self.window.applied
        self.window.close()
        self.dialog.deleteLater()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()
        for name in ('apply', 'pause', 'resume', 'prepare_upgrade', 'restore', 'set_startup'):
            getattr(self.backend, name).assert_not_called()
        self.backend.backend.stop.assert_not_called()
        self.temp.cleanup()

    def test_cursor_sidebar_and_busy_block_handoff_without_runtime_mutation(self):
        from dataclasses import replace
        from pointer.ui.main_window import _ready_for_upgrade
        for state, detail in (('cursor', '光标'), ('sidebar', '工作台外观'), ('busy', '当前操作')):
            with self.subTest(state=state):
                self.window.busy = state == 'busy'
                self.window.sidebar_dirty = state == 'sidebar'
                self.window._draft = replace(self.window.applied, size=48) if state == 'cursor' else self.window.applied
                with patch('pointer.ui.update_dialog.trigger_silent_upgrade') as launch:
                    self.dialog._on_download_finished('mock installer')
                launch.assert_not_called()
                self.assertFalse(_ready_for_upgrade(self.window))
                self.assertEqual(self.dialog.stage, 'preflight')
                self.assertIn(detail, self.dialog.error_details.toPlainText())
                self.assertTrue(self.dialog.update_btn.isEnabled())
        self.window.sidebar_dirty = False

    def test_draft_busy_and_thread_cleanup_block_before_creating_download_worker(self):
        from dataclasses import replace
        try:
            for state in ('cursor', 'sidebar', 'busy', 'cleanup'):
                with self.subTest(state=state):
                    self.window.busy = state == 'busy'
                    self.window.sidebar_dirty = state == 'sidebar'
                    self.window._threads = [(Mock(), Mock())] if state == 'cleanup' else []
                    self.window._draft = replace(self.window.applied, size=48) if state == 'cursor' else self.window.applied
                    with patch('pointer.ui.update_dialog.DownloadWorker') as worker, \
                         patch('pointer.ui.update_dialog.trigger_silent_upgrade') as launch:
                        self.dialog._start_download()
                    worker.assert_not_called()
                    launch.assert_not_called()
                    self.assertIsNone(self.dialog.worker)
                    self.assertEqual(self.dialog.stage, 'preflight')
        finally:
            self.window._threads = []
            self.window.sidebar_dirty = False

    def test_state_changes_during_download_are_checked_again_before_install(self):
        from dataclasses import replace
        for state in ('cursor', 'sidebar', 'busy'):
            with self.subTest(state=state):
                self.window.busy = self.window.sidebar_dirty = False
                self.window._draft = self.window.applied
                self.dialog._downloaded_installer = None
                self.dialog.worker = None
                with patch('pointer.ui.update_dialog.DownloadWorker') as worker, \
                     patch('pointer.ui.update_dialog.trigger_silent_upgrade') as launch:
                    worker.return_value.isRunning.return_value = False
                    self.dialog._start_download()
                    worker.return_value.start.assert_called_once()
                    self.window.busy = state == 'busy'
                    self.window.sidebar_dirty = state == 'sidebar'
                    if state == 'cursor':
                        self.window._draft = replace(self.window.applied, size=48)
                    self.dialog._on_download_finished('mock installer')
                    launch.assert_not_called()
                self.assertEqual(self.dialog.stage, 'preflight')
        self.window.sidebar_dirty = False

    def test_launch_failure_is_not_download_failure_and_retries_same_package(self):
        long_error = 'CreateProcess failed: ' + 'very_long_path_segment/' * 120
        with patch('pointer.ui.update_dialog.trigger_silent_upgrade', side_effect=OSError(long_error)) as launch, \
             patch.object(self.window, '_finish_upgrade') as finish:
            self.dialog._on_download_finished('mock installer')
        self.assertEqual(self.dialog.stage, 'launch')
        self.assertIn('安装器启动失败', self.dialog.status_lbl.text())
        self.assertNotIn('下载失败', self.dialog.status_lbl.text())
        self.assertEqual(self.dialog.error_details.toPlainText(), long_error)
        finish.assert_not_called()
        launch.assert_called_once_with('mock installer', self.backend, expected_sha256='a' * 64, expected_size=8)
        with patch('pointer.ui.update_dialog.trigger_silent_upgrade') as launch, \
             patch('pointer.ui.update_dialog.DownloadWorker') as download, \
             patch.object(self.window, '_finish_upgrade') as finish:
            self.dialog._start_download()
        download.assert_not_called()
        launch.assert_called_once()
        finish.assert_called_once()
        self.assertTrue(self.dialog._closed)

    def test_missing_cached_package_clears_install_retry_and_downloads_again(self):
        from pathlib import Path
        missing = Path(self.temp.name) / 'missing-installer.exe'
        with patch('pointer.ui.update_dialog.trigger_silent_upgrade', side_effect=FileNotFoundError(str(missing))):
            self.dialog._on_download_finished(str(missing))
        self.assertEqual(self.dialog.stage, 'download')
        self.assertIsNone(self.dialog._downloaded_installer)
        self.assertEqual(self.dialog.update_btn.text(), '重试下载')
        with patch('pointer.ui.update_dialog.DownloadWorker') as worker, \
             patch('pointer.ui.update_dialog.trigger_silent_upgrade') as launch:
            worker.return_value.isRunning.return_value = False
            self.dialog._start_download()
            worker.return_value.start.assert_called_once()
            launch.assert_not_called()

    def test_createprocess_file_not_found_keeps_existing_package_for_retry(self):
        from pathlib import Path
        package = Path(self.temp.name) / 'installer.exe'
        package.write_bytes(b'verified')
        with patch('pointer.ui.update_dialog.trigger_silent_upgrade', side_effect=FileNotFoundError('loader unavailable')):
            self.dialog._on_download_finished(str(package))
        self.assertEqual(self.dialog.stage, 'launch')
        self.assertEqual(self.dialog._downloaded_installer, str(package))
        self.assertEqual(self.dialog.update_btn.text(), '重试安装')
        with patch('pointer.ui.update_dialog.DownloadWorker') as worker, \
             patch('pointer.ui.update_dialog.trigger_silent_upgrade') as launch, \
             patch.object(self.window, '_finish_upgrade') as finish:
            self.dialog._start_download()
            worker.assert_not_called()
            launch.assert_called_once()
            finish.assert_called_once()

    def test_changed_local_package_is_verification_failure_and_requires_redownload(self):
        from pointer.updater import ChecksumMismatchError
        with patch('pointer.ui.update_dialog.trigger_silent_upgrade', side_effect=ChecksumMismatchError('changed bytes')):
            self.dialog._on_download_finished('mock installer')
        self.assertEqual(self.dialog.stage, 'verification')
        self.assertIsNone(self.dialog._downloaded_installer)
        self.assertEqual(self.dialog.update_btn.text(), '重试下载')

    def test_skip_persists_only_version_and_keeps_cursor_and_startup_drafts(self):
        from dataclasses import replace
        self.window.change(size=48, startup=False, auto_check_update=True, tray_enabled=True)
        draft = self.window.draft()
        self.window._prewarm_timer.stop()
        self.dialog._skip_version()
        self.assertTrue(self.dialog._closed)
        self.assertEqual(self.backend.store.load(), replace(self.settings, skip_update_version='9.0.0'))
        self.assertEqual(self.window.draft(), replace(draft, skip_update_version='9.0.0'))
        self.assertEqual(self.window.applied, replace(self.settings, skip_update_version='9.0.0'))
        self.assertFalse(self.window._prewarm_timer.isActive())
        reopened = MainWindow(self.backend)
        reopened.status_timer.stop()
        reopened._prewarm_timer.stop()
        reopened._show_update_dialog = Mock()
        reopened.show()
        reopened._update_check_completed({'available': True, 'latest_version': '9.0.0'}, '', False)
        reopened._show_update_dialog.assert_not_called()
        reopened.close()
        reopened.deleteLater()

    def test_skip_save_failure_retains_drafts_and_can_retry(self):
        self.window.change(size=48)
        draft, applied = self.window.draft(), self.window.applied
        with patch.object(self.backend.store, 'save', side_effect=OSError('settings write denied')):
            self.dialog._skip_version()
        self.assertFalse(self.dialog._closed)
        self.assertEqual(self.dialog.stage, 'preference')
        self.assertIn('settings write denied', self.dialog.error_details.toPlainText())
        self.assertEqual((self.window.draft(), self.window.applied), (draft, applied))
        self.dialog._skip_version()
        self.assertTrue(self.dialog._closed)
        self.assertEqual(self.window.draft().size, 48)

    def test_skip_readback_failure_does_not_acknowledge_saved_state(self):
        applied = self.window.applied
        with patch.object(self.backend.store, 'load', side_effect=[self.settings, OSError('readback failed')]):
            self.dialog._skip_version()
        self.assertFalse(self.dialog._closed)
        self.assertEqual(self.window.applied, applied)
        self.assertIn('readback failed', self.dialog.error_details.toPlainText())
        self.dialog._skip_version()
        self.assertTrue(self.dialog._closed)

    def test_corrupt_saved_preferences_are_not_overwritten_by_skip(self):
        self.backend.store.path.write_text('{broken', encoding='utf-8')
        self.dialog._skip_version()
        self.assertFalse(self.dialog._closed)
        self.assertEqual(self.backend.store.path.read_text(encoding='utf-8'), '{broken')
        self.assertEqual(self.window.applied, self.settings)

    def test_skip_while_busy_does_not_write(self):
        self.window.busy = True
        with patch.object(self.backend.store, 'save') as save:
            self.dialog._skip_version()
        save.assert_not_called()
        self.assertFalse(self.dialog._closed)
        self.assertIn('当前操作', self.dialog.error_details.toPlainText())

    def test_download_passes_hash_and_size_to_worker(self):
        with patch('pointer.ui.update_dialog.DownloadWorker') as worker:
            self.dialog._start_download()
        self.assertEqual(worker.call_args.kwargs, {'expected_sha256': 'a' * 64, 'expected_size': 8})
        first_target = worker.call_args.args[1]
        self.assertEqual(first_target.parts[-3:], ('updates', 'a' * 64, 'Pointer-setup.exe'))
        self.assertEqual(self.dialog.later_btn.text(), '取消下载')
        self.assertTrue(self.dialog.later_btn.isEnabled())
        second = UpdateDialog(dict(INSTALL_INFO, expected_sha256='B' * 64), self.backend, self.window)
        try:
            with patch('pointer.ui.update_dialog.DownloadWorker') as worker:
                second._start_download()
            self.assertEqual(worker.call_args.args[1].parts[-3:], ('updates', 'b' * 64, 'Pointer-setup.exe'))
            self.assertNotEqual(worker.call_args.args[1], first_target)
        finally:
            second.reject()
            second.deleteLater()

    def test_theme_and_long_details_do_not_force_dialog_beyond_viewport(self):
        from PySide6.QtGui import QPalette
        from pointer.ui.colors import theme_colors
        for dark in (False, True):
            self.window.ui_dark = dark
            dialog = UpdateDialog(INSTALL_INFO, self.backend, self.window)
            detail = '<raw error> ' + 'unbroken_' * 300
            dialog._show_error('launch', '安装器启动失败', detail)
            dialog.resize(480, 560)
            dialog.show()
            APP.processEvents()
            self.assertEqual(dialog.palette().color(QPalette.ColorRole.Window).name(), theme_colors(dark)['canvas'])
            self.assertEqual(dialog.error_details.toPlainText(), detail)
            self.assertLessEqual(dialog.minimumSizeHint().width(), 480)
            self.assertEqual(dialog.error_details.horizontalScrollBar().maximum(), 0)
            self.assertTrue(dialog.rect().contains(dialog.update_btn.geometry()))
            self.assertGreater(dialog.maximumWidth(), dialog.minimumWidth())
            dialog.reject()
            dialog.deleteLater()


if __name__ == '__main__':
    unittest.main()
