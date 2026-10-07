import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock, patch
from dataclasses import replace
from PySide6.QtCore import Qt, QEvent, QEventLoop, QTimer
from PySide6.QtWidgets import QApplication, QScrollArea, QLineEdit, QToolButton
from PySide6.QtTest import QTest
from pointer.cursor.settings import CursorSettings
from pointer.ui.main_window import MainWindow
from pointer.ui.pages.appearance import PRESETS, WORKSPACE_PRESETS
from pointer.cursor.resources import canvas_size

APP = QApplication.instance() or QApplication([])


class CommercialWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.window = MainWindow(self.backend)
        self.window.show()
        APP.processEvents()

    def tearDown(self):
        self.window.discard_changes()
        self.window.close()

    def test_one_inspector_scroll_keeps_preview_and_adjacent_actions_fixed(self):
        self.window.resize(880, 620)
        APP.processEvents()
        scroll = self.window.stack.widget(0)
        self.assertEqual(len(self.window.pages[0].findChildren(QScrollArea)), 0)
        before = self.window.preview.geometry()
        scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
        APP.processEvents()
        self.assertEqual(self.window.preview.geometry(), before)
        a = self.window.apply_button.mapTo(self.window, self.window.apply_button.rect().center())
        b = self.window.discard.mapTo(self.window, self.window.discard.rect().center())
        self.assertEqual(a.y(), b.y())
        self.assertLess(abs(a.x() - b.x()), 130)
        self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)

    def test_new_shell_targets_and_preview_choices_fit_narrow_window(self):
        self.window.resize(880, 620)
        APP.processEvents()
        APP.processEvents()
        for button in self.window.navigation:
            self.assertGreaterEqual(button.height(), 40)
            self.assertGreaterEqual(button.width(), 88)
        scroll = self.window.stack.widget(0)
        for button, _ in self.window.pages[0].preset_buttons:
            scroll.ensureWidgetVisible(button)
            APP.processEvents()
            point = button.mapTo(scroll.viewport(), button.rect().center())
            self.assertTrue(scroll.viewport().rect().contains(point), 'curated palette unreachable by inspector scroll')
        for button in self.window.preview.findChildren(QToolButton):
            if button.property('segmented'):
                self.assertGreaterEqual(button.width(), button.fontMetrics().horizontalAdvance(button.text()) + 6)
                self.assertTrue(button.parentWidget().rect().contains(button.geometry()))

    def test_legacy_theme_load_does_not_rewrite_saved_colors_or_style(self):
        original = CursorSettings(style='pixel', light_body='#12092b', light_outline='#ff007f',
                                  dark_body='#00f0ff', dark_outline='#7928ca')
        self.window.set_draft(original)
        self.assertEqual(self.window.draft(), original)
        self.assertFalse(self.window.pages[0].legacy_style.isHidden())
        self.window.toggle_workspace_theme()
        self.assertEqual(self.window.draft(), original)
        self.backend.apply.assert_not_called()

    def test_retired_outline_remains_unchanged_and_reachable_in_history(self):
        original = replace(self.window.draft(), style='outline', light_body='#123456', strength=35)
        self.window.set_draft(original)
        page = self.window.pages[0]
        self.assertNotIn('outline', page.shape_buttons)
        self.assertGreaterEqual(page.legacy_style.findData('outline'), 0)
        self.assertFalse(page.legacy_style.isHidden())
        self.window.toggle_workspace_theme()
        self.assertEqual(self.window.draft(), original)
        self.backend.apply.assert_not_called()

    def test_retired_trail_configuration_is_preserved_but_visibly_inactive(self):
        original = replace(self.window.draft(), motion='trail', strength=70)
        self.window.set_draft(original)
        self.window.select_page(1)
        page = self.window.pages[1]
        self.assertEqual(self.window.draft(), original)
        self.assertFalse(page.retired_hint.isHidden())
        self.assertIn('停用', page.mode.currentText())
        self.assertFalse(page.sliders['strength'][0].isEnabled())
        self.backend.apply.assert_not_called()

    def test_all_families_cancel_and_reduced_motion_resume_without_reviving_press(self):
        from pointer.cursor.art.families import RECOMMENDED_STYLES
        self.window.preview.timer.stop()
        for style in RECOMMENDED_STYLES:
            for reduced in (False, True):
                self.window.change(style=style)
                self.window.reduce_motion = reduced
                panel = self.window.preview
                surface = panel.surfaces[0]
                QTest.mousePress(surface, Qt.MouseButton.LeftButton, pos=surface.rect().center())
                for now in (1.0, 1.061):
                    with patch('pointer.ui.preview.time.monotonic', return_value=now):
                        panel.tick()
                self.assertTrue(panel.down)
                self.assertEqual(panel.frame, 0 if reduced else 4)
                QApplication.sendEvent(surface, QEvent(QEvent.Type.WindowDeactivate))
                self.assertFalse(panel.down)
                self.assertFalse(surface.pressed)
                self.window.reduce_motion = False
                for now in (1.061, 1.3):
                    with patch('pointer.ui.preview.time.monotonic', return_value=now):
                        panel.tick()
                self.assertEqual(panel.frame, 0, (style, reduced))
                QTest.mouseRelease(surface, Qt.MouseButton.LeftButton, pos=surface.rect().center())
        self.backend.apply.assert_not_called()

    def test_reduced_motion_keeps_immediate_press_feedback_without_cursor_animation(self):
        self.window.reduce_motion = True
        surface = self.window.preview.surfaces[0]
        QTest.mousePress(surface, Qt.MouseButton.LeftButton, pos=surface.rect().center())
        self.window.preview.tick()
        self.assertTrue(surface.pressed)
        self.assertEqual(self.window.preview.frame, 0)
        QTest.mouseRelease(surface, Qt.MouseButton.LeftButton, pos=surface.rect().center())
        self.assertFalse(surface.pressed)
        self.assertEqual(self.window.preview.frame, 0)

    def test_palette_custom_reset_preserves_other_draft_and_hover_is_observation(self):
        page = self.window.pages[0]
        aurora = next(p for p in PRESETS if p['id'] == 'aurora')
        self.window.change(style='pixel', size=64, motion='shrink', strength=75)
        before = self.window.draft()
        QTest.mouseMove(page.preset_buttons[1][0], page.preset_buttons[1][0].rect().center())
        self.assertEqual(self.window.draft(), before)
        page.apply_preset(aurora)
        page.edit_color('light_outline', '#123456')
        self.assertIn('自定义', page.palette_name.text())
        self.assertIn('极光', page.palette_name.text())
        self.assertFalse(any(button.isChecked() for button, _ in page.preset_buttons + page.trendy_preset_buttons))
        page.restore_palette()
        for field in ('style', 'size', 'motion', 'strength'):
            self.assertEqual(getattr(self.window.draft(), field), getattr(before, field))
        self.assertEqual(self.window.draft().light_outline, aurora['light_outline'])
        self.backend.apply.assert_not_called()

    def test_role_background_and_scale_leave_draft_unchanged(self):
        before = self.window.draft()
        self.window.preview.role.setCurrentIndex(16)
        self.window.preview.background.setCurrentIndex(1)
        self.window.preview.scale.setCurrentIndex(1)
        self.assertEqual(self.window.draft(), before)
        self.backend.apply.assert_not_called()

    def test_legacy_style_remains_reachable_after_new_style_is_applied(self):
        page = self.window.pages[0]
        self.window.change(style='pixel', light_body='#123456', size=48)
        original = self.window.draft()
        self.assertTrue(page.legacy_toggle.isChecked())
        page.legacy_toggle.setChecked(False)
        self.window.sync()
        self.assertTrue(page.legacy_style.isHidden())
        page.shape_buttons['quill'].click()
        new = self.window.draft()
        self.backend.apply.return_value = {'settings': new.to_dict(), 'running': False}
        self.window.apply_draft()
        loop = QEventLoop()
        QTimer.singleShot(250, loop.quit)
        loop.exec()
        self.assertFalse(self.window.busy)
        self.backend.apply.assert_called_once_with(new, preserve_runtime=True)
        page.legacy_toggle.setChecked(False)
        self.assertFalse(page.legacy_toggle.isHidden())
        page.legacy_toggle.click()
        APP.processEvents()
        self.assertFalse(page.legacy_style.isHidden())
        page.legacy_style.setCurrentIndex(page.legacy_style.findData('pixel'))
        self.assertEqual(self.window.draft(), original)
        self.assertEqual(self.window.applied.style, 'quill')
        self.assertEqual(self.backend.apply.call_count, 1)

    def test_palette_selection_matching_and_reset_preserve_glow(self):
        page = self.window.pages[0]
        aurora = next(p for p in WORKSPACE_PRESETS if p['id'] == 'slate')
        self.window.change(aura_glow=True, aura_color='#123456')
        page.apply_preset(aurora)
        self.assertTrue(self.window.draft().aura_glow)
        self.assertEqual(self.window.draft().aura_color, '#123456')
        self.assertTrue(next(b for b, p in page.preset_buttons if p['id'] == 'slate').isChecked())
        page.edit_color('light_body', '#654321')
        page.restore_palette()
        self.assertTrue(self.window.draft().aura_glow)
        self.assertEqual(self.window.draft().aura_color, '#123456')
        self.backend.apply.assert_not_called()

    def test_preview_mouse_hover_and_press_have_distinct_pixels_without_motion(self):
        self.window.change(motion='off')
        surface = self.window.preview.surfaces[0]
        surface.hovered = surface.pressed = False
        normal = surface.grab().toImage()
        surface.hovered = True
        hovered = surface.grab().toImage()
        QTest.mousePress(surface, Qt.MouseButton.LeftButton, pos=surface.rect().center())
        pressed = surface.grab().toImage()
        self.assertNotEqual(normal, hovered)
        self.assertNotEqual(hovered, pressed)
        QTest.mouseRelease(surface, Qt.MouseButton.LeftButton, pos=surface.rect().center())
        self.assertFalse(surface.pressed)
        self.backend.apply.assert_not_called()

    def test_actual_size_64_does_not_reuse_enlarged_cache_or_clip(self):
        self.window.resize(880, 620)
        self.window.change(size=64)
        APP.processEvents()
        self.window.preview.scale.setCurrentIndex(1)
        APP.processEvents()
        for surface in self.window.preview.surfaces:
            surface.grab()
            self.assertTrue(surface.rect().contains(surface.cursor_bounds.toAlignedRect()))
            self.assertAlmostEqual(surface.cursor_bounds.width(), canvas_size(self.window.draft()), delta=1)

    def test_invalid_color_and_enter_never_submit_system(self):
        page = self.window.pages[0]
        page.open_advanced()
        APP.processEvents()
        field = page.color_fields['light_body']
        field.setText('#123456')
        QTest.keyClick(field, Qt.Key.Key_Return)
        field.setText('invalid')
        QTest.keyClick(field, Qt.Key.Key_Return)
        self.assertFalse(self.window.apply_button.isEnabled())
        self.window.apply_draft()
        self.backend.apply.assert_not_called()
        self.assertEqual(self.window.draft().light_body, '#123456')

    def test_explicit_apply_is_once_and_preserves_runtime_contract(self):
        self.window.change(size=40)
        desired = self.window.draft()
        self.backend.apply.return_value = {'settings': desired.to_dict(), 'running': False}
        self.window.apply_draft()
        self.window.apply_draft()
        loop = QEventLoop()
        poll = QTimer()
        poll.setInterval(10)
        poll.timeout.connect(lambda: loop.quit() if not self.window.busy and not self.window._threads else None)
        poll.start()
        QTimer.singleShot(3000, loop.quit)
        loop.exec()
        poll.stop()
        self.backend.apply.assert_called_once_with(desired, preserve_runtime=True)
        self.backend.resume.assert_not_called()
        self.assertEqual(self.window.draft(), self.window.applied)
        self.window.apply_draft()
        self.assertEqual(self.backend.apply.call_count, 1)

    def test_reduced_motion_toast_closes_without_animation(self):
        self.window.reduce_motion = True
        self.window.toast.show_message('Test')
        self.window.toast._fade_out()
        self.assertFalse(self.window.toast.isVisible())
        self.assertIsNone(self.window.toast.anim)

    def test_narrow_motion_controls_remain_inside_inspector(self):
        self.window.resize(880, 620)
        self.window.select_page(1)
        APP.processEvents()
        scroll = self.window.stack.widget(1)
        self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
        page = self.window.pages[1]
        for control in (page.mode, *(s[0] for s in page.sliders.values())):
            self.assertTrue(page.rect().contains(control.geometry()))

    def test_preset_rows_do_not_overlap_after_narrow_resize_in_both_themes(self):
        page = self.window.pages[0]
        for dark in (False, True):
            if self.window.ui_dark != dark:
                self.window.toggle_workspace_theme()
            self.window.resize(1180, 800)
            APP.processEvents()
            self.window.resize(880, 620)
            APP.processEvents()
            APP.processEvents()
            self.assertEqual(page._preset_columns, 3)
            buttons = [b for b, _ in page.preset_buttons + page.trendy_preset_buttons]
            for a, b in zip(buttons, buttons[1:]):
                self.assertGreaterEqual(a.height(), 58)
                self.assertFalse(a.geometry().intersects(b.geometry()))

    def test_failed_apply_keeps_draft_and_retry_clears_error(self):
        self.window.change(size=40)
        desired = self.window.draft()
        self.window.operation_failed('Mock failure')
        self.assertEqual(self.window.draft(), desired)
        self.assertNotEqual(self.window.draft(), self.window.applied)
        self.assertTrue(self.window.feedback.property('error'))
        self.window._replace_draft = True
        self.window._operation_message = 'Mock success'
        self.window.operation_done({'settings': desired.to_dict(), 'running': False})
        self.assertFalse(self.window.feedback.property('error'))
        self.assertEqual(self.window.draft(), self.window.applied)
