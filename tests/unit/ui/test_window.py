import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import importlib.util
import time
import unittest
from unittest.mock import Mock
from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSlider, QPushButton
from pointer.cursor.settings import CursorSettings
from shiboken6 import isValid

QT_APP = QApplication.instance() or QApplication([])


class WindowTests(unittest.TestCase):
    def release_window(self, window):
        if not isValid(window):
            return
        deadline = time.monotonic() + 3
        while window._threads and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertEqual(window._threads, [], 'Native operation thread did not finish')
        window._draft = window.applied
        self.assertTrue(window.close())
        window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def tearDown(self):
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def make_window(self):
        from pointer.ui.main_window import MainWindow
        application = Mock()
        application.settings.return_value = CursorSettings()
        application.backend.snapshot.return_value = {'running':False,'startup_enabled':False}
        window = MainWindow(application)
        self.addCleanup(self.release_window, window)
        return window, application

    def test_async_failure_keeps_draft_and_restores_controls(self):
        window, application = self.make_window()
        application.apply.side_effect = RuntimeError('not ready')
        window.change(strength=75)
        window.apply_draft()
        self.assertTrue(window.busy)
        loop = QEventLoop()
        poll = QTimer()
        poll.setInterval(10)
        poll.timeout.connect(lambda: loop.quit() if not window.busy and not window._threads else None)
        poll.start()
        QTimer.singleShot(3000, loop.quit)
        loop.exec()
        poll.stop()
        self.assertFalse(window.busy)
        self.assertEqual(window.draft().strength,75)
        self.assertIn('not ready',window.feedback.text())
        self.assertTrue(window.stack.isEnabled())
        window.discard_changes()
        window.close()

    def test_material_operation_callbacks_run_on_the_gui_thread(self):
        import tempfile
        import threading
        from pathlib import Path
        from PySide6.QtCore import QThread, Slot
        from pointer.application import Application
        from pointer.ui.material_workspace import MaterialWindow
        from pointer.ui.sidebar_settings import SidebarStore

        class ThreadCheckedWindow(MaterialWindow):
            @Slot(object)
            def operation_done(self, result):
                self.deliveries.append(('done', threading.get_ident()))
                if QThread.currentThread() == QT_APP.thread():
                    super().operation_done(result)

            @Slot(str)
            def operation_failed(self, error):
                self.deliveries.append(('failed', threading.get_ident()))
                if QThread.currentThread() == QT_APP.thread():
                    super().operation_failed(error)

        for failure in (False, True):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                backend = Mock()
                backend.startup_enabled.return_value = False
                backend.runtime_status.return_value = {'running': False}
                if failure:
                    backend.stop.side_effect = RuntimeError('mock pause failed')
                application = Application(root / 'data', root / 'install', backend=backend)
                application.store.save(CursorSettings(tray_enabled=False, auto_check_update=False))
                saved = application.store.path.read_bytes()
                window = ThreadCheckedWindow(application, sidebar_store=SidebarStore(root / 'sidebar.json'))
                window.deliveries = []
                window.status_timer.stop()
                window._prewarm_timer.stop()
                worker_threads = []
                gui_thread = threading.get_ident()

                def operation():
                    worker_threads.append(threading.get_ident())
                    return application.pause()

                try:
                    window.change(strength=75)
                    window._prewarm_timer.stop()
                    window.run_operation(operation, 'paused')
                    loop = QEventLoop()
                    poll = QTimer()
                    poll.setInterval(10)
                    poll.timeout.connect(lambda: loop.quit() if not window.busy and not window._threads else None)
                    poll.start()
                    QTimer.singleShot(3000, loop.quit)
                    loop.exec()
                    poll.stop()
                    self.assertEqual(len(worker_threads), 1)
                    self.assertNotEqual(worker_threads[0], gui_thread)
                    self.assertEqual(window.deliveries, [('failed' if failure else 'done', gui_thread)])
                    self.assertFalse(window.busy)
                    self.assertEqual(window._threads, [])
                    self.assertTrue(window.stack.isEnabled())
                    self.assertEqual(window.draft().strength, 75)
                    self.assertEqual(application.store.path.read_bytes(), saved)
                    self.assertIn('mock pause failed' if failure else 'paused', window.feedback.text())
                    backend.stop.assert_called_once()
                    backend.apply.assert_not_called()
                    backend.set_startup.assert_not_called()
                finally:
                    for thread, _worker in window._threads:
                        thread.quit()
                        thread.wait(3000)
                    window.busy = False
                    window._draft = window.applied
                    window.close()
                    window.deleteLater()
                    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                    QT_APP.processEvents()

    def test_close_and_upgrade_wait_for_native_thread_teardown(self):
        import threading
        import time
        from unittest.mock import patch
        from PySide6.QtCore import Qt
        from pointer.ui.main_window import MainWindow

        application = Mock()
        application.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        application.runtime_status.return_value = {'running': False}
        window = MainWindow(application)
        window.status_timer.stop()
        window._prewarm_timer.stop()
        window.show()
        operation_gate, teardown_gate, teardown_entered = (threading.Event() for _ in range(3))

        def operation():
            operation_gate.wait(3)
            return {}

        def hold_native_teardown():
            teardown_entered.set()
            teardown_gate.wait(3)

        def wait_for(predicate):
            deadline = time.monotonic() + 2
            while time.monotonic() < deadline and not predicate():
                QTest.qWait(10)
            self.assertTrue(predicate())

        with patch.object(QT_APP, 'quit') as quit_app:
            try:
                window.run_operation(operation, 'done')
                thread, worker = window._threads[0]
                thread.finished.connect(hold_native_teardown, Qt.ConnectionType.DirectConnection)
                operation_gate.set()
                wait_for(lambda: teardown_entered.is_set() and not window.busy)
                self.assertEqual(window._threads, [(thread, worker)])
                self.assertFalse(window._ready_for_upgrade())
                self.assertFalse(window.close())
                self.assertTrue(window.isVisible())
                window._finish_upgrade()
                QTest.qWait(20)
                quit_app.assert_not_called()
                self.assertEqual(window._threads, [(thread, worker)])
                teardown_gate.set()
                wait_for(lambda: bool(quit_app.call_count))
                quit_app.assert_called_once()
                self.assertEqual(window._threads, [])
                self.assertFalse(window.isVisible())
                application.pause.assert_not_called()
                application.backend.stop.assert_not_called()
            finally:
                operation_gate.set()
                teardown_gate.set()
                for thread, _worker in window._threads:
                    thread.quit()
                    thread.wait(3000)
                QT_APP.processEvents()
                window.close()
                window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                QT_APP.processEvents()

    def test_normal_close_does_not_pause_background_service(self):
        window, application = self.make_window()
        window.close()
        application.pause.assert_not_called()
        application.restore.assert_not_called()

    def test_pause_result_preserves_unapplied_draft(self):
        window, application = self.make_window()
        window.change(strength=75)
        window._operation_message = 'paused'
        window.operation_done({'running':False,'settings':CursorSettings().to_dict()})
        self.assertEqual(window.draft().strength,75)
        self.assertEqual(window.applied.strength,50)
        window.discard_changes();window.close()

    def test_draft_edit_does_not_apply_system_configuration(self):
        self.assertIsNotNone(importlib.util.find_spec('pointer.ui'), 'GUI missing')
        from pointer.ui.main_window import MainWindow
        application = Mock()
        application.settings.return_value = CursorSettings()
        application.snapshot.return_value = {'running':False, 'startup_enabled':False}
        window = MainWindow(application)
        window.findChild(QSlider, 'strengthSlider').setValue(75)
        self.assertEqual(window.draft().strength, 75)
        application.apply.assert_not_called()
        self.assertTrue(window.findChild(QPushButton, 'applyButton').isEnabled())
        window.discard_changes()
        self.assertEqual(window.draft().strength, 50)
        window.close()

    def test_draft_change_schedules_prewarm_without_calling_apply(self):
        window, application = self.make_window()
        window.change(strength=75)
        self.assertTrue(window._prewarm_timer.isActive())
        window._trigger_prewarm()
        application.prewarm.assert_called_once()
        application.apply.assert_not_called()
        window.discard_changes()
        window.close()

    def test_discrete_setting_change_waits_for_input_to_settle(self):
        window, application = self.make_window()
        window.change(light_body="#123456")
        self.assertTrue(window._prewarm_timer.isActive())
        self.assertGreaterEqual(window._prewarm_timer.interval(), 1000)
        window.discard_changes()
        window.close()

    def test_start_preset_prewarm_schedules_only_current_draft(self):
        window, application = self.make_window()
        window.start_preset_prewarm()
        self.assertTrue(window._prewarm_timer.isActive())
        application.prewarm.assert_not_called()
        window._trigger_prewarm()
        import time
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and application.prewarm.call_count == 0:
            time.sleep(0.02)
        application.prewarm.assert_called_once_with(window.draft())
        window.close()

    def test_runtime_status_hook_uses_one_query_and_clears_stale_snapshot(self):
        window, application = self.make_window()
        window.status_timer.stop()
        window._runtime_status_updated = Mock()
        application.runtime_status.reset_mock()
        application.runtime_status.return_value = {'running': True, 'effects_paused': False}
        window.refresh_status()
        application.runtime_status.assert_called_once()
        self.assertEqual(window._last_runtime_state, {'running': True, 'effects_paused': False})
        self.assertEqual(window._last_runtime_error, '')
        window._runtime_status_updated.assert_called_once()
        application.runtime_status.side_effect = OSError('status unavailable')
        window.refresh_status()
        self.assertIsNone(window._last_runtime_state)
        self.assertEqual(window._last_runtime_error, 'status unavailable')
        application.runtime_status.reset_mock()
        window.busy = True
        window.refresh_status()
        application.runtime_status.assert_not_called()
        self.assertEqual(window._runtime_status_updated.call_count, 3)
        window.busy = False
        window.close()

    def test_finish_upgrade_only_closes_gui_and_never_stops_runtime(self):
        from unittest.mock import patch
        window, application = self.make_window()
        with patch.object(QT_APP, 'quit') as quit_app:
            window._finish_upgrade()
        quit_app.assert_called_once()
        application.prepare_upgrade.assert_not_called()
        application.pause.assert_not_called()
        application.backend.stop.assert_not_called()

    def test_scheme_operations_are_silent_by_default(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch, Mock
        from pathlib import Path
        from pointer.windows import scheme
        f = io.StringIO()
        with redirect_stdout(f):
            with patch.object(scheme, 'read_values', return_value={}), \
                 patch.object(scheme, 'reload_cursors'), \
                 patch.object(scheme, 'validate_backup', return_value={}), \
                 patch.object(scheme, 'restore_values'), \
                 patch.object(scheme, 'save_backup'), \
                 patch.object(scheme.winreg, 'CreateKeyEx'), \
                 patch.object(scheme.winreg, 'OpenKey'), \
                 patch.object(scheme.winreg, 'SetValueEx'), \
                 patch.object(scheme.USER32, 'LoadImageW', return_value=1234), \
                 patch.object(scheme.USER32, 'DestroyCursor'), \
                 patch.object(Path, 'is_file', return_value=True), \
                 patch.object(Path, 'exists', return_value=False), \
                 patch.object(Path, 'read_text', return_value='{}'):
                scheme.restore(Path('dummy.json'))
                fake_cur = Mock()
                fake_cur.is_file.return_value = True
                fake_cur.read_bytes.return_value = b'\0' * 64
                scheme.apply_paths({'Arrow': fake_cur}, backup_path=Path('dummy.json'))
        self.assertEqual(f.getvalue(), '')
