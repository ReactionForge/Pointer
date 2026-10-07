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
        self.window.status_timer.stop()
        self.window._prewarm_timer.stop()
        self.window.preview.timer.stop()
        self.window.toast.show_message = Mock()
        self.window._show_update_dialog = Mock()
        self.window.show()
        APP.processEvents()
        self.page = self.window.pages[3]

    def tearDown(self):
        if isValid(self.window):
            self.window.discard_changes()
            self.window.close()
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
        self.window.close()
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
    def test_download_status_claims_checksum_verification_only_with_an_expected_digest(self):
        for expected in (None, 'a' * 64):
            with self.subTest(expected=expected):
                dialog = UpdateDialog({'latest_version': '9.0.0', 'expected_sha256': expected})
                statuses = []
                def prevented_install(*args):
                    statuses.append(dialog.status_lbl.text())
                    raise RuntimeError('fixture prevents installation')
                with patch('pointer.ui.update_dialog.trigger_silent_upgrade', side_effect=prevented_install):
                    dialog._on_download_finished('mock installer path')
                self.assertEqual('完整性校验通过' in statuses[0], expected is not None)
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
                dialog = UpdateDialog({'latest_version': '9.0.0', 'download_url': 'https://invalid.example/update.exe'})
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
                        APP.processEvents()


if __name__ == '__main__':
    unittest.main()
