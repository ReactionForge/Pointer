"""Tray persistence and draft semantics, without creating a native tray icon."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from dataclasses import replace
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from pointer.cursor.settings import CursorSettings
from pointer.ui.main_window import MainWindow
from pointer.ui.tray import TrayController

APP = QApplication.instance() or QApplication([])


class TrayLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.backend.runtime_status.return_value = {'running': True}
        self.window = MainWindow(self.backend)
        self.window.status_timer.stop()
        self.window._prewarm_timer.stop()
        self.window.preview.timer.stop()

    def tearDown(self):
        self.window.busy = False
        self.window._draft = self.window.applied
        self.window.close()
        if self.window.tray_controller:
            self.window.tray_controller.dispose()
            self.window.tray_controller = None
        self.window.deleteLater()
        APP.processEvents()
        self.backend.apply.assert_not_called()
        self.backend.pause.assert_not_called()
        self.backend.restore.assert_not_called()

    def test_saved_tray_toggle_reconciles_both_directions_once(self):
        with patch('pointer.ui.tray.TrayController') as controller:
            self.window.change(tray_enabled=True)
            controller.assert_not_called()
            self.window._operation_message = 'saved'
            self.window._replace_draft = True
            self.window.operation_done({'settings': self.window.draft().to_dict()})
            controller.assert_called_once_with(self.window)
            first = self.window.tray_controller
            for _ in range(3):
                self.window.sync()
            controller.assert_called_once()
            self.window.change(tray_enabled=False)
            first.dispose.assert_not_called()
            self.window.operation_done({'settings': self.window.draft().to_dict()})
            first.dispose.assert_called_once()
            self.assertIsNone(self.window.tray_controller)
            self.window.sync()
            first.dispose.assert_called_once()
            self.window.change(tray_enabled=True)
            self.window.operation_done({'settings': self.window.draft().to_dict()})
            self.assertEqual(controller.call_count, 2)

    def make_controller(self):
        with patch('pointer.ui.tray.QSystemTrayIcon.isSystemTrayAvailable', return_value=False):
            controller = TrayController(self.window)
        controller.tray = Mock()
        controller.update_menu()
        return controller

    def test_menu_reuses_actions_and_labels_unapplied_draft(self):
        controller = self.make_controller()
        self.window.tray_controller = controller
        # Keep the saved preference on while editing unrelated cursor fields.
        self.window.applied = replace(self.window.applied, tray_enabled=True)
        self.window._draft = self.window.applied
        menu = controller.menu
        action = next(action for action, field, value in controller._choices if field == 'motion' and value == 'shrink')
        action.trigger()
        self.assertEqual(self.window.draft().motion, 'shrink')
        self.assertNotEqual(self.window.applied.motion, 'shrink')
        self.assertIn('未应用草稿', controller.draft_status.text())
        self.assertTrue(action.isChecked())
        self.assertTrue(controller.apply_action.isEnabled())
        controller.update_menu()
        self.assertIs(controller.menu, menu)
        controller.tray.setContextMenu.assert_called_once()
        texts = [action.text() for action in menu.actions()]
        self.assertIn('关闭工作台（后台继续运行）', texts)
        self.assertFalse(any('退出 Pointer' in text for text in texts))

    def test_busy_menu_cannot_edit_or_apply_draft(self):
        controller = self.make_controller()
        self.window.tray_controller = controller
        self.window.applied = replace(self.window.applied, tray_enabled=True)
        self.window._draft = self.window.applied
        self.window.busy = True
        controller.update_menu()
        original = self.window.draft()
        for action, _, _ in controller._choices:
            self.assertFalse(action.isEnabled())
        controller._edit_draft(motion='shrink')
        self.assertEqual(self.window.draft(), original)
        self.assertFalse(controller.apply_action.isEnabled())
        self.assertFalse(controller.update_action.isEnabled())

    def test_dispose_releases_icon_and_menu_once(self):
        controller = self.make_controller()
        icon = controller.tray
        controller.dispose()
        controller.dispose()
        icon.hide.assert_called_once()
        icon.deleteLater.assert_called_once()
        self.assertIsNone(controller.menu)
        self.assertIsNone(controller.tray)
