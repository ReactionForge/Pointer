"""Approved shell geometry, themes and guarded data/operation boundaries."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from dataclasses import asdict
from unittest.mock import Mock, patch
from PySide6.QtCore import QPoint, Qt, QEvent, QCoreApplication
from PySide6.QtGui import QColor, QPalette, QCloseEvent
from PySide6.QtWidgets import QApplication, QFrame, QMessageBox
from pointer.cursor.settings import CursorSettings
from pointer.ui.approved_workspace import approved_colors
from pointer.ui.confirmations import confirmation_box
from scripts.capture_dual_ui import SafeDualWindow
from scripts.safe_preview import isolated_update_services
from PySide6.QtTest import QTest
from pointer.ui.family_workspace import cursor_pixmap

APP = QApplication.instance() or QApplication([])


class DualWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.window = SafeDualWindow(self.backend)
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
            for width, height in ((880, 620), (1180, 880), (1800, 900)):
                self.window.resize(width, height)
                for page in (0, 3):
                    self.window.select_page(page)
                    APP.processEvents()
                    # QScrollArea posts a second layout request after the
                    # responsive palette changes its minimum-size hint.
                    APP.processEvents()
                    self.assertEqual((self.window.width(), self.window.height()), (width, height))
                    self.assertEqual(self.window.stack.widget(page).horizontalScrollBar().maximum(), 0)
                    self.assertLessEqual(self.window.content_widget.width(), 1100)
                    self.assertEqual(self.window.findChild(QFrame, 'controlBar').height(), 52)
                    self.assertTrue(self.window.apply_button.isVisible())
                    self.assertEqual(self.window.draft(), original)
                    if page == 0:
                        self.assertEqual(self.window.shape_gallery.columns, 3)
                        scroll = self.window.stack.widget(0)
                        self.assertLessEqual(self.window.pages[0].width(), scroll.viewport().width()+2)
                        before = self.window.preview.mapTo(self.window, QPoint())
                        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
                        APP.processEvents()
                        self.assertEqual(self.window.preview.mapTo(self.window, QPoint()), before)
                        self.assertTrue(self.window.preview.isVisible())
                        scroll.verticalScrollBar().setValue(0)
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

    def test_clean_stage_uses_exact_original_pixmap_and_contains_64px_bounds(self):
        self.window.change(size=64)
        self.window.preview.timer.stop()
        for role in ('arrow', 'hand', 'ibeam', 'busy'):
            self.window.preview.role.setCurrentIndex(self.window.preview.role.findData(role))
            for frame in range(5) if role in ('arrow', 'hand') else (0,):
                self.window.preview.frame = frame
                for surface in self.window.preview.surfaces:
                    surface.repaint()
                    APP.processEvents()
                    key = surface.last_cursor_key
                    settings, current_role, theme, current_frame, actual, dpi = key
                    self.assertTrue(actual)
                    expected = cursor_pixmap(settings, current_role, theme, current_frame, crop=False, dpi=dpi)
                    expected.setDevicePixelRatio(dpi/96)
                    self.assertEqual(self.window.preview.get_cached_pixmap(key).toImage(), expected.toImage())
                    self.assertTrue(surface.rect().contains(surface.cursor_bounds.toRect()))
        self.backend.apply.assert_not_called()

    def test_trial_and_stage_press_cancel_without_apply_or_reactivation(self):
        trial = self.window.trial_button
        QTest.mousePress(trial, Qt.MouseButton.LeftButton)
        self.assertTrue(self.window.preview.down)
        QCoreApplication.sendEvent(trial, QEvent(QEvent.Type.Leave))
        self.assertFalse(self.window.preview.down)
        QTest.mouseRelease(trial, Qt.MouseButton.LeftButton)
        stage = self.window.preview.surfaces[0]
        stage.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyPress(stage, Qt.Key.Key_Space)
        self.assertTrue(self.window.preview.down)
        self.window.select_page(3)
        self.assertFalse(self.window.preview.down)
        self.window.select_page(0)
        self.assertFalse(self.window.preview.down)
        self.backend.apply.assert_not_called()

    def test_running_preview_survives_whole_window_theme_and_resize_captures(self):
        # Exercise the live timer through a parent-window snapshot; child-only
        # cache checks cannot catch an empty stage in a composed window.
        for dark in (False, True, False):
            if self.window.ui_dark != dark:
                self.window.toggle_workspace_theme()
            for width in (880, 1180):
                self.window.resize(width, 880)
                QTest.qWait(60)
                image = self.window.grab().toImage()
                for surface in self.window.preview.surfaces:
                    origin = surface.mapTo(self.window, QPoint())
                    bounds = surface.cursor_bounds.toRect().translated(origin)
                    background = QColor('#eef0f5' if surface.theme == 'light' else '#202329')
                    cursor_pixels = sum(image.pixelColor(x, y) != background
                        for y in range(bounds.top(), bounds.bottom()+1)
                        for x in range(bounds.left(), bounds.right()+1))
                    self.assertGreater(cursor_pixels, 20)
                    label_pixels = sum(image.pixelColor(origin.x()+x, origin.y()+y) != background
                        for y in range(13, 30) for x in range(12, surface.width()-12))
                    self.assertGreater(label_pixels, 20)
        self.backend.apply.assert_not_called()
