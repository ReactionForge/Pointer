import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import importlib.util
import unittest
from unittest.mock import Mock
from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QSlider, QPushButton
from pointer.cursor.settings import CursorSettings

QT_APP = QApplication.instance() or QApplication([])


class WindowTests(unittest.TestCase):
    def make_window(self):
        from pointer.ui.main_window import MainWindow
        application = Mock()
        application.settings.return_value = CursorSettings()
        application.backend.snapshot.return_value = {'running':False,'startup_enabled':False}
        return MainWindow(application), application

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
