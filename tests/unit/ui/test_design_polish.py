import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock
from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QPalette, QColor, QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QDialog
from pointer.cursor.settings import CursorSettings
from pointer.ui.main_window import MainWindow

APP = QApplication.instance() or QApplication([])


def contrast(first, second):
    def luminance(color):
        values = [color.redF(), color.greenF(), color.blueF()]
        linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in values]
        return sum(v * w for v, w in zip(linear, (.2126, .7152, .0722)))
    a, b = sorted((luminance(first), luminance(second)))
    return (b + .05) / (a + .05)


class DesignPolishTests(unittest.TestCase):
    def setUp(self):
        backend = Mock()
        backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.window = MainWindow(backend)
        self.window.show()
        APP.processEvents()

    def tearDown(self):
        self.window.discard_changes()
        self.window.close()

    def test_light_settings_text_has_readable_theme_colors(self):
        self.window.select_page(3)
        APP.processEvents()
        for name in ('rowTitle', 'rowSubtitle', 'sectionTitle'):
            labels = self.window.pages[3].findChildren(QLabel, name)
            self.assertTrue(labels)
            for label in labels:
                self.assertGreaterEqual(contrast(label.palette().color(QPalette.ColorRole.WindowText), QColor('#ffffff')), 4.5)

    def test_dark_drag_label_is_readable_on_its_actual_surface(self):
        self.window.toggle_workspace_theme()
        self.window.select_page(2)
        surface = self.window.pages[2].scenario('drag')
        APP.processEvents()
        background = surface.grab().toImage().pixelColor(surface.width() // 2, surface.height() // 2)
        self.assertGreaterEqual(contrast(surface.label.palette().color(QPalette.ColorRole.WindowText), background), 4.5)

    def test_off_switch_boundary_is_visible_in_both_themes(self):
        self.window.select_page(3)
        switch = self.window.pages[3].startup
        for dark in (False, True):
            if self.window.ui_dark != dark:
                self.window.toggle_workspace_theme()
            APP.processEvents()
            track = switch.grab().toImage().pixelColor(20, 5)
            self.assertGreaterEqual(contrast(track, QColor('#25262b' if dark else '#ffffff')), 3)

    def test_palette_is_inline_and_color_validation_preserves_draft(self):
        page = self.window.pages[0]
        page.palette_button.click()
        APP.processEvents()
        visible_dialogs = [w for w in QApplication.topLevelWidgets() if isinstance(w, QDialog) and w.isVisible()]
        self.assertEqual(visible_dialogs, [])
        field = page.findChild(QLineEdit, 'customColor_light_body')
        self.assertIsNotNone(field)
        original = self.window.draft()
        field.setText('#123456')
        field.editingFinished.emit()
        self.assertEqual(self.window.draft().light_body, '#123456')
        self.assertEqual(self.window.applied.light_body, '#000000')
        field.setText('#bad-input')
        field.editingFinished.emit()
        self.assertEqual(self.window.draft().light_body, '#123456')
        page.cancel_colors.click()
        self.assertEqual(self.window.draft(), original)

    def test_mouse_focus_is_not_rendered_as_keyboard_focus(self):
        button = self.window.theme_button
        button.setFocus(Qt.FocusReason.MouseFocusReason)
        APP.processEvents()
        self.assertFalse(bool(button.property('keyboardFocus')))
        button.clearFocus()
        button.setFocus(Qt.FocusReason.TabFocusReason)
        APP.processEvents()
        self.assertTrue(bool(button.property('keyboardFocus')))

    def test_inline_colors_fit_narrow_window_and_preserve_apply(self):
        self.window.resize(880, 620)
        page = self.window.pages[0]
        page.open_advanced()
        APP.processEvents()
        APP.processEvents()
        viewport = self.window.stack.widget(0).viewport()
        self.assertEqual(len(page.preset_buttons + page.trendy_preset_buttons), 8)
        for field in page.color_fields.values():
            rectangle = field.rect()
            self.assertTrue(viewport.rect().contains(field.mapTo(viewport, rectangle.topLeft())))
            self.assertTrue(viewport.rect().contains(field.mapTo(viewport, rectangle.bottomRight())))
        self.assertTrue(self.window.apply_button.isVisible())

    def test_rgb_validation_discard_and_focus_loss_do_not_reapply_old_color(self):
        page = self.window.pages[0]
        page.open_advanced()
        APP.processEvents()
        field = page.color_fields['light_body']
        field.setText('rgb(18,52,86)')
        field.editingFinished.emit()
        self.assertEqual(self.window.draft().light_body, '#123456')
        for invalid in ('rgb(256,0,0)', 'rgb(1,2,3', '1,2,3)', '#123'):
            field.setText(invalid)
            field.editingFinished.emit()
            self.assertEqual(self.window.draft().light_body, '#123456')
        self.window.discard_changes()
        field.clearFocus()
        APP.processEvents()
        self.assertEqual(self.window.draft(), self.window.applied)

    def test_successful_apply_ends_color_revert_session(self):
        page = self.window.pages[0]
        page.open_advanced()
        APP.processEvents()
        page.edit_color('light_body', '#123456')
        self.window._replace_draft = True
        self.window._operation_message = '隔离测试完成'
        self.window.operation_done({'settings': self.window.draft().to_dict()})
        page.cancel_color_edit()
        self.assertEqual(self.window.draft(), self.window.applied)
        self.assertEqual(self.window.applied.light_body, '#123456')

    def test_preview_keyboard_press_repeat_release_blur_and_page_change(self):
        surface = self.window.preview.hero
        surface.setFocus(Qt.FocusReason.TabFocusReason)
        APP.processEvents()
        self.assertTrue(surface.hasFocus())
        self.assertTrue(surface.property('keyboardFocus'))
        QTest.keyPress(surface, Qt.Key.Key_Space)
        self.assertTrue(surface.pressed)
        self.assertTrue(self.window.preview.down)
        repeat_release = QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier, ' ', True)
        QApplication.sendEvent(surface, repeat_release)
        self.assertTrue(self.window.preview.down)
        QTest.keyRelease(surface, Qt.Key.Key_Space)
        self.assertFalse(surface.pressed)
        self.assertFalse(self.window.preview.down)
        QTest.keyPress(surface, Qt.Key.Key_Space)
        self.window.theme_button.setFocus(Qt.FocusReason.TabFocusReason)
        APP.processEvents()
        self.assertFalse(surface.pressed)
        self.assertFalse(self.window.preview.down)
        surface.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyPress(surface, Qt.Key.Key_Space)
        self.window.select_page(3)
        self.assertFalse(surface.pressed)
        self.assertFalse(self.window.preview.down)

    def test_preview_focus_ring_is_painted_in_both_themes(self):
        from pointer.ui.colors import theme_colors
        surface = self.window.preview.hero
        for dark in (False, True):
            if self.window.ui_dark != dark:
                self.window.toggle_workspace_theme()
            surface.setFocus(Qt.FocusReason.TabFocusReason)
            APP.processEvents()
            image = surface.grab().toImage()
            expected = QColor(theme_colors(surface.theme == 'dark')['focus'])
            self.assertEqual(image.pixelColor(surface.width() // 2, 2).name(), expected.name())
            for paired in self.window.preview.surfaces:
                paired.setFocus(Qt.FocusReason.TabFocusReason)
                APP.processEvents()
                expected = QColor(theme_colors(paired.theme == 'dark')['focus'])
                self.assertEqual(paired.grab().toImage().pixelColor(paired.width() // 2, 2).name(), expected.name())

    def test_role_menu_contains_last_role_and_fits_narrow_viewport(self):
        self.window.resize(880, 620)
        combo = self.window.preview.role
        combo.showPopup()
        APP.processEvents()
        self.assertEqual(combo.count(), 17)
        last = combo.model().index(16, 0)
        combo.view().scrollTo(last)
        APP.processEvents()
        rect = combo.view().visualRect(last)
        self.assertTrue(combo.view().viewport().rect().contains(rect.center()))
        self.assertLessEqual(combo.view().horizontalScrollBar().maximum(), 0)
        combo.hidePopup()

    def test_disabled_switch_paints_the_theme_border_in_both_themes(self):
        from pointer.ui.colors import theme_colors
        self.window.select_page(3)
        switch = self.window.pages[3].startup
        switch.setEnabled(False)
        for dark in (False, True):
            if self.window.ui_dark != dark:
                self.window.toggle_workspace_theme()
            APP.processEvents()
            image = switch.grab().toImage()
            expected = QColor(theme_colors(dark)['border'])
            self.assertEqual(image.pixelColor(20, 0).name(), expected.name())
