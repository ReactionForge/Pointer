"""Real menu actions, without showing or touching the Windows system tray."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication, QWidget
from pointer.cursor.settings import CursorSettings
from pointer.ui.tray import TrayController

APP = QApplication.instance() or QApplication([])


class TrayMotionTests(unittest.TestCase):
    def setUp(self):
        self.window = QWidget()
        self.settings = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.window.draft = lambda: self.settings
        def change(**fields):
            self.settings = replace(self.settings, **fields)
        self.window.change = Mock(side_effect=change)
        with patch('pointer.ui.tray.QSystemTrayIcon.isSystemTrayAvailable', return_value=False):
            self.controller = TrayController(self.window)
        self.controller.tray = Mock()

    def tearDown(self):
        self.window.close()

    def actions(self):
        self.controller.update_menu()
        menu = self.controller.tray.setContextMenu.call_args.args[0]
        for action in menu.actions():
            submenu = action.menu()
            if submenu and any(a.data() == 'tilt' for a in submenu.actions()):
                return submenu.actions()
        self.fail('Motion submenu missing')

    def test_only_supported_modes_are_selectable_and_their_actual_actions_edit_draft(self):
        actions = self.actions()
        self.assertEqual({a.data() for a in actions if a.isEnabled()}, {'tilt', 'shrink', 'spring', 'off'})
        for mode in ('shrink', 'spring', 'off', 'tilt'):
            next(a for a in self.actions() if a.data() == mode).trigger()
            self.window.change.assert_called_with(motion=mode)
            self.assertEqual(self.settings.motion, mode)
            self.assertTrue(next(a for a in self.actions() if a.data() == mode).isChecked())

    def test_retired_settings_show_disabled_status_and_cannot_be_selected_or_mutated(self):
        for mode in ('pulse', 'trail'):
            with self.subTest(mode=mode):
                self.settings = replace(self.settings, motion=mode, strength=70)
                original = self.settings
                self.window.change.reset_mock()
                actions = self.actions()
                self.assertFalse(any(a.data() in ('pulse', 'trail') for a in actions))
                status = next(a for a in actions if a.data() == 'retired_overlay')
                self.assertFalse(status.isEnabled())
                self.assertTrue(status.isChecked())
                status.trigger()
                self.window.change.assert_not_called()
                self.assertEqual(self.settings, original)
                self.assertEqual(CursorSettings.from_dict(self.settings.to_dict()), original)

    def test_quit_cancel_preserves_tray_and_does_not_quit_application(self):
        with patch.object(self.window, 'close', return_value=False):
            # QApplication is imported inside the handler; patch that provider.
            with patch('PySide6.QtWidgets.QApplication.instance') as application:
                self.controller._quit_application()
        self.controller.tray.hide.assert_not_called()
        application.assert_not_called()

    def test_quit_acceptance_closes_window_before_hiding_and_quitting(self):
        order = []
        application = Mock()
        application.quit.side_effect = lambda: order.append('quit')
        self.controller.tray.hide.side_effect = lambda: order.append('tray')
        with patch.object(self.window, 'close', side_effect=lambda: order.append('close') or True), \
             patch('PySide6.QtWidgets.QApplication.instance', return_value=application):
            self.controller._quit_application()
        self.assertEqual(order, ['close', 'tray', 'quit'])
