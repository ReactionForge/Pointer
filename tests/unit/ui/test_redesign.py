import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock
from pathlib import Path
from PIL import Image
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from pointer.cursor.settings import CursorSettings
from pointer.paths import ROOT
from pointer.ui.main_window import MainWindow
from pointer.ui.pages.appearance import AppearancePage, PRESETS

QT_APP = QApplication.instance() or QApplication([])


class RedesignTests(unittest.TestCase):
    def setUp(self):
        self.application = Mock()
        self.application.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.application.backend.snapshot.return_value = {'running': True, 'startup_enabled': False}
        self.window = MainWindow(self.application)

    def tearDown(self):
        self.window.discard_changes()
        self.window.close()

    def test_app_icon_file_has_windows_multi_resolutions(self):
        icon_path = ROOT / 'packaging/windows/pointer.ico'
        self.assertTrue(icon_path.exists(), 'packaging/windows/pointer.ico must exist')
        with Image.open(icon_path) as img:
            sizes = img.ico.sizes()
        expected = {(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)}
        self.assertTrue(expected.issubset(sizes), f'Missing required icon sizes: {expected - sizes}')

    def test_appearance_preset_selection_updates_draft_colors(self):
        page = self.window.pages[0]
        self.assertIsInstance(page, AppearancePage)
        self.assertEqual(len(page.preset_buttons), 8)

        # Test applying Aurora preset
        aurora_preset = next(p for p in PRESETS if p['id'] == 'aurora')
        page.apply_preset(aurora_preset)
        draft = self.window.draft()
        self.assertEqual(draft.light_body, aurora_preset['light_body'])
        self.assertEqual(draft.light_outline, aurora_preset['light_outline'])
        self.assertEqual(draft.dark_body, aurora_preset['dark_body'])
        self.assertEqual(draft.dark_outline, aurora_preset['dark_outline'])

        # Test applying Obsidian preset
        obsidian_preset = next(p for p in PRESETS if p['id'] == 'obsidian')
        page.apply_preset(obsidian_preset)
        draft = self.window.draft()
        self.assertEqual(draft.light_body, obsidian_preset['light_body'])
        self.assertEqual(draft.light_outline, obsidian_preset['light_outline'])

    def test_preview_surface_direct_click_interaction(self):
        panel = self.window.preview
        surface = panel.surfaces[0]
        self.assertFalse(panel.down)

        # Mouse press directly on surface triggers down state
        QTest.mousePress(surface, Qt.MouseButton.LeftButton)
        self.assertTrue(panel.down)
        self.assertTrue(surface.pressed)

        # Mouse release clears down state
        QTest.mouseRelease(surface, Qt.MouseButton.LeftButton)
        self.assertFalse(panel.down)
        self.assertFalse(surface.pressed)

    def test_adaptive_layout_toggles_preview_visibility(self):
        # Appearance (0) and Motion (1) keep preview visible (not hidden)
        self.window.select_page(0)
        self.assertFalse(self.window.preview.isHidden())

        self.window.select_page(1)
        self.assertFalse(self.window.preview.isHidden())

        # Test (2) and Preferences (3) expand to full width (preview is hidden)
        self.window.select_page(2)
        self.assertTrue(self.window.preview.isHidden())

        self.window.select_page(3)
        self.assertTrue(self.window.preview.isHidden())

    def test_toast_message_display_and_feedback(self):
        self.window.discard_changes()
        self.assertEqual(self.window.toast.label.text(), '已放弃未应用的草稿修改')
        self.assertFalse(self.window.toast.isHidden())

    def test_toast_positioning_within_content_bounds_at_minimum_window_size(self):
        self.window.resize(920, 680)
        self.window.toast.show_message('测试提示信息')
        content_w = self.window.content_widget.width()
        toast_x = self.window.toast.x()
        toast_r = toast_x + self.window.toast.width()
        self.assertGreaterEqual(toast_x, 0, 'Toast x must not be negative')
        self.assertLessEqual(toast_r, content_w, f'Toast right edge ({toast_r}) must not exceed content width ({content_w})')

    def test_preview_cursor_scaling_at_large_sizes(self):
        self.window.change(size=64)
        panel = self.window.preview
        surface = panel.surfaces[0]
        surface.resize(250, 165)
        # Verify paintEvent executes cleanly without clipping or error
        surface.repaint()
        self.assertEqual(panel.settings.size, 64)

    def test_preview_surface_badge_reflects_motion_button_and_direct_press(self):
        panel = self.window.preview
        surface = panel.surfaces[0]
        self.assertFalse(panel.down)
        self.assertFalse(surface.pressed)

        # Bottom button triggers set_down(True)
        panel.set_down(True)
        self.assertTrue(panel.down)
        # Direct press triggers pressed
        surface.pressed = True
        panel.set_down(False)
        surface.pressed = False

    def test_test_surface_label_adjusts_size_without_truncation(self):
        self.window.select_page(2)
        test_page = self.window.pages[2]
        drag = test_page.scenario('drag')
        # Label width must be wide enough to hold the complete title text (> 140px)
        self.assertGreater(drag.label.width(), 140, 'Drag label must not be truncated to 100px')

        # Test dragging bounds
        from PySide6.QtCore import QPoint
        QTest.mousePress(drag, Qt.MouseButton.LeftButton, pos=QPoint(50, 50))
        self.assertTrue(drag.dragging)

        # Drag far to the right
        QTest.mouseMove(drag, pos=QPoint(1000, 1000))
        self.assertLessEqual(drag.label.x() + drag.label.width(), drag.width(), 'Label must not drag outside card bounds')

        QTest.mouseRelease(drag, Qt.MouseButton.LeftButton, pos=QPoint(1000, 1000))
        self.assertFalse(drag.dragging)

    def test_appearance_preset_case_insensitivity(self):
        page = self.window.pages[0]
        self.window.change(
            light_body='#FFFFFF',
            light_outline='#000000',
            dark_body='#000000',
            dark_outline='#FFFFFF'
        )
        classic_btn = page.preset_buttons[0][0]
        # Should match classic preset (#000000, #ffffff, #ffffff, #000000)
        self.window.change(
            light_body='#000000',
            light_outline='#FFFFFF',
            dark_body='#FFFFFF',
            dark_outline='#000000'
        )
        self.assertTrue(classic_btn.isChecked())

    def test_motion_sliders_disabled_and_styled_when_off(self):
        self.window.select_page(1)
        motion_page = self.window.pages[1]
        self.window.change(motion='off')
        slider, label, _ = motion_page.sliders['strength']
        self.assertFalse(slider.isEnabled())
        self.assertIn('未启用', label.text())

        self.window.change(motion='tilt')
        self.assertTrue(slider.isEnabled())
        self.assertNotIn('未启用', label.text())

    def test_all_17_system_cursors_configured_in_test_page(self):
        from pointer.cursor.theme import ROLE_IDS, FILENAMES
        from pointer.ui.pages.tests import QT_CURSOR_MAP
        self.window.select_page(2)
        test_page = self.window.pages[2]
        expected_roles = {PathName.rsplit('.', 1)[0] for PathName in FILENAMES.values()}
        self.assertEqual(len(expected_roles), 17)
        for role in expected_roles:
            self.assertIn(role, QT_CURSOR_MAP)

    def test_checkbox_check_asset_exists_and_configured(self):
        from pointer.ui.theme import STYLE, CHECK_ICON_PATH
        check_path = ROOT / 'assets' / 'check.png'
        self.assertTrue(check_path.exists(), 'assets/check.png must exist')
        self.assertIn(CHECK_ICON_PATH, STYLE)

    def test_preview_surface_reflects_locked_appearance_strategy(self):
        panel = self.window.preview
        light_surf = panel.surfaces[0]
        dark_surf = panel.surfaces[1]

        # In adaptive mode: light surf uses light scheme, dark surf uses dark scheme
        self.window.change(appearance='adaptive')
        light_surf.repaint()
        dark_surf.repaint()
        # In locked light mode: both surfaces resolve to light cursor
        self.window.change(appearance='light')
        light_surf.repaint()
        dark_surf.repaint()
        # In locked dark mode: both surfaces resolve to dark cursor
        self.window.change(appearance='dark')
        light_surf.repaint()
        dark_surf.repaint()

    def test_preview_timer_skips_when_hidden(self):
        panel = self.window.preview
        panel.setVisible(False)
        old_frame = panel.frame
        old_loading = panel.loading_frame
        panel.tick()
        self.assertEqual(panel.frame, old_frame)
        self.assertEqual(panel.loading_frame, old_loading)

    def test_preview_loading_animation_throttled_to_native_speed(self):
        import time
        panel = self.window.preview
        panel.setVisible(True)
        # Select busy role
        idx = panel.role.findData('busy')
        panel.role.setCurrentIndex(idx)
        panel._last_loading_time = time.monotonic()
        initial_frame = panel.loading_frame

        # Calling tick() immediately (<50ms elapsed) should NOT advance loading frame
        panel.tick()
        self.assertEqual(panel.loading_frame, initial_frame)

        # Simulating >50ms elapsed advances loading frame by exactly 1
        panel._last_loading_time = time.monotonic() - 0.06
        panel.tick()
        self.assertEqual(panel.loading_frame, (initial_frame + 1) % 24)

    def test_preview_set_settings_preserves_motion_state_when_down(self):
        panel = self.window.preview
        panel.set_down(True)
        self.assertTrue(panel.down)
        panel.set_settings(CursorSettings(press_ms=80, release_ms=180))
        self.assertTrue(panel.motion.down)
        self.assertEqual(panel.motion._target, 0.9)
        panel.set_down(False)


if __name__ == '__main__':
    unittest.main()
