"""Approved shell geometry, themes and guarded data/operation boundaries."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from dataclasses import asdict
from unittest.mock import Mock, patch
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPalette, QCloseEvent
from PySide6.QtWidgets import QApplication, QFrame, QMessageBox
from pointer.cursor.settings import CursorSettings
from pointer.ui.approved_workspace import approved_colors
from pointer.ui.confirmations import confirmation_box
from scripts.capture_approved_ui import SafeApprovedWindow
from scripts.safe_preview import isolated_update_services

APP = QApplication.instance() or QApplication([])


class ApprovedWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.window = SafeApprovedWindow(self.backend)
        self.window.status_timer.stop()
        self.window._prewarm_timer.stop()
        self.window.show()
        APP.processEvents()

    def tearDown(self):
        self.window.discard_changes()
        self.window.close()

    def test_both_pages_at_three_widths_keep_native_frame_fixed_apply_and_original_data(self):
        original = self.window.draft()
        self.assertTrue(self.window.ui_dark)
        for dark in (True, False):
            if self.window.ui_dark != dark: self.window.toggle_workspace_theme()
            for width, height in ((880, 620), (1100, 830), (1800, 900)):
                self.window.resize(width, height)
                for page in (0, 3):
                    self.window.select_page(page)
                    APP.processEvents()
                    self.assertEqual((self.window.width(), self.window.height()), (width, height))
                    self.assertEqual(self.window.stack.widget(page).horizontalScrollBar().maximum(), 0)
                    self.assertLessEqual(self.window.content_widget.width(), 960)
                    self.assertEqual(self.window.findChild(QFrame, 'controlBar').height(), 52)
                    self.assertTrue(self.window.apply_button.isVisible())
                    self.assertEqual(self.window.draft(), original)
                    if page == 0:
                        preview_x = self.window.preview.mapTo(self.window, QPoint()).x()
                        for frame in self.window.pages[0].findChildren(QFrame, 'approvedGroup'):
                            self.assertLessEqual(abs(frame.mapTo(self.window, QPoint()).x()-preview_x), 2)
                        self.assertEqual(self.window.shape_gallery.columns, 6)
        self.assertFalse(self.window.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.backend.apply.assert_not_called()

    def test_real_family_palette_history_and_custom_controls_only_change_draft(self):
        page = self.window.pages[0]
        original = asdict(self.window.draft())
        page.shape_buttons['quill'].click()
        after = asdict(self.window.draft())
        self.assertEqual({key for key in original if original[key] != after[key]}, {'style'})
        page.preset_buttons[1][0].click()
        after_palette = asdict(self.window.draft())
        self.assertLessEqual({key for key in after if after[key] != after_palette[key]},
                             {'light_body', 'light_outline', 'dark_body', 'dark_outline'})
        page.legacy_toggle.click()
        self.assertTrue(page.legacy_style.isVisible())
        page.palette_button.click()
        APP.processEvents()
        self.assertTrue(page.inline_colors.isVisible())
        self.assertTrue(self.window.preview.isVisible())
        self.assertTrue(self.window.apply_button.isVisible())
        self.backend.apply.assert_not_called()

    def test_owned_confirmation_four_theme_combinations_and_close_cancel_keep_draft(self):
        original_palette = APP.palette()
        try:
            for system_dark in (False, True):
                palette = QPalette(original_palette)
                palette.setColor(QPalette.ColorRole.Window, QColor('#202020' if system_dark else '#ffffff'))
                palette.setColor(QPalette.ColorRole.WindowText, QColor('#ffffff' if system_dark else '#202126'))
                APP.setPalette(palette)
                for dark in (False, True):
                    if self.window.ui_dark != dark: self.window.toggle_workspace_theme()
                    box = confirmation_box(self.window, '未应用的修改', '放弃未应用的修改并关闭窗口？', '放弃修改', '继续编辑')
                    self.assertEqual(box.palette().color(QPalette.ColorRole.Window).name(), approved_colors(dark)['canvas'])
                    self.assertEqual(box.palette().color(QPalette.ColorRole.WindowText).name(), approved_colors(dark)['text'])
                    self.assertIs(box.defaultButton(), box.button(QMessageBox.StandardButton.No))
                    self.assertIs(box.escapeButton(), box.button(QMessageBox.StandardButton.No))
                    box.deleteLater()
            self.window.change(size=48)
            draft = self.window.draft()
            with patch('pointer.ui.main_window.ask_confirmation', return_value=QMessageBox.StandardButton.No):
                event = QCloseEvent()
                self.window.closeEvent(event)
                self.assertFalse(event.isAccepted())
                self.assertEqual(self.window.draft(), draft)
        finally:
            APP.setPalette(original_palette)
        self.backend.apply.assert_not_called()

    def test_new_entry_update_button_and_callbacks_remain_guarded(self):
        with patch('pointer.updater.check_for_updates') as check, isolated_update_services():
            self.window.select_page(3)
            self.window.pages[3].check_update_btn.click()
            self.window._check_update_silent_startup()
            self.window._show_update_dialog({'available': True})
            self.assertEqual(self.window._threads, [])
            check.assert_not_called()
        self.backend.apply.assert_not_called()
