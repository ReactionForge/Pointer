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
