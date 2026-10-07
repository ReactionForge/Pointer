"""Two-page review shell keeps data/operation semantics and safe entry isolation."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock, patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from pointer.cursor.settings import CursorSettings
from scripts.capture_reference_ui import SafeReferenceWindow
from scripts.safe_preview import isolated_update_services, ISOLATED_UPDATE_MESSAGE

APP = QApplication.instance() or QApplication([])


class ReferenceWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.window = SafeReferenceWindow(self.backend)
        self.window.status_timer.stop()
        self.window._prewarm_timer.stop()
        self.window.show()
        APP.processEvents()

    def tearDown(self):
        self.window.discard_changes()
        self.window.close()

    def test_reference_pages_fit_two_widths_without_data_changes_or_frameless_window(self):
        original = self.window.draft()
        for width, height in ((880, 620), (1180, 800), (1800, 900)):
            self.window.resize(width, height)
            for page in (0, 3):
                self.window.select_page(page)
                APP.processEvents()
                self.assertEqual((self.window.width(), self.window.height()), (width, height))
                self.assertEqual(self.window.nav_rail.width(), 190)
                self.assertEqual(self.window.stack.widget(page).horizontalScrollBar().maximum(), 0)
                for button in self.window.navigation:
                    self.assertGreaterEqual(button.height(), 34)
                self.assertEqual(self.window.draft(), original)
                self.assertLessEqual(self.window.content_widget.width(), 960)
                if page == 0:
                    buttons = list(self.window.pages[0].shape_buttons.values())
                    self.assertEqual(self.window.shape_gallery.columns, 6)
                    self.assertLess(buttons[0].x(), 24)
                    self.assertLessEqual(max(b.width() for b in buttons)-min(b.width() for b in buttons), 1)
                    scroll = self.window.stack.widget(0)
                    for palette, _ in self.window.pages[0].preset_buttons:
                        self.assertLessEqual(palette.mapTo(scroll.viewport(), palette.rect().bottomRight()).y(), scroll.viewport().height())
        self.assertFalse(self.window.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertEqual(len(self.window.pages[0].shape_buttons), 6)
        self.assertEqual(len(self.window.pages[0].preset_buttons), 8)
        self.backend.apply.assert_not_called()

    def test_role_scale_background_and_theme_are_observation_only_and_64px_has_room(self):
        self.window.change(size=64)
        original = self.window.draft()
        self.window.preview.role.setCurrentIndex(4)
        self.window.preview.background.setCurrentIndex(1)
        self.window.toggle_workspace_theme()
        APP.processEvents()
        self.assertEqual(self.window.draft(), original)
        from pointer.cursor.resources import canvas_size
        self.assertGreaterEqual(self.window.preview.surfaces[1].height(), canvas_size(original)+24)
        self.backend.apply.assert_not_called()

    def test_reference_settings_update_button_and_callbacks_stay_isolated(self):
        with patch('pointer.updater.check_for_updates') as check, isolated_update_services():
            self.window.select_page(3)
            self.window.pages[3].check_update_btn.click()
            self.window._check_update_silent_startup()
            self.window._show_update_dialog({'available': True})
            self.assertEqual(self.window.feedback.text(), ISOLATED_UPDATE_MESSAGE)
            self.assertEqual(self.window._threads, [])
            check.assert_not_called()
            self.backend.apply.assert_not_called()
