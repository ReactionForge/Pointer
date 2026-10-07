"""Explicit window theme choices preserve cursor and sidebar drafts."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock

from PySide6.QtCore import Qt, QPoint
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QPushButton
from pointer.cursor.settings import CursorSettings
from scripts.capture_material_ui import SafeMaterialWindow

APP = QApplication.instance() or QApplication([])


class ThemeSelectorTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.window = SafeMaterialWindow(self.backend)
        self.window.status_timer.stop()
        self.window._prewarm_timer.stop()
        self.window.preview.timer.stop()
        self.window.select_page(3)
        self.window.show()
        APP.processEvents()

    def tearDown(self):
        self.window.cancel_sidebar_settings()
        self.window.discard_changes()
        self.window.close()
        for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
            getattr(self.backend, name).assert_not_called()

    def selector(self):
        selector = getattr(self.window, 'theme_selector', None)
        self.assertIsNotNone(selector, 'Window theme needs explicit light and dark choices')
        return selector

    def test_explicit_and_repeated_choices_preserve_both_drafts(self):
        w = self.window
        selector = self.selector()
        w.change(size=48)
        draft = w.draft()
        saved = w.applied
        sidebar = w.sidebar_appearance
        selector.buttons[True].click()
        self.assertTrue(w.ui_dark)
        self.assertTrue(selector.buttons[True].isChecked())
        selector.buttons[False].click()
        self.assertFalse(w.ui_dark)
        self.assertTrue(selector.buttons[False].isChecked())
        selector.buttons[False].click()
        self.assertFalse(w.ui_dark)
        self.assertTrue(selector.buttons[False].isChecked())
        self.assertFalse(selector.buttons[True].isChecked())
        self.assertEqual(w.draft(), draft)
        self.assertEqual(w.applied, saved)
        self.assertEqual(w.sidebar_appearance, sidebar)
        self.assertFalse(w.sidebar_dirty)

    def test_keyboard_selects_with_arrows_enter_and_space(self):
        w = self.window
        selector = self.selector()
        selector.buttons[False].click()
        light = selector.buttons[False]
        dark = selector.buttons[True]
        light.setFocus(Qt.FocusReason.TabFocusReason)
        APP.processEvents()
        QTest.keyClick(light, Qt.Key.Key_Right)
        self.assertTrue(w.ui_dark)
        self.assertTrue(dark.hasFocus())
        self.assertTrue(bool(dark.property('keyboardFocus')))
        QTest.keyClick(dark, Qt.Key.Key_Home)
        self.assertFalse(w.ui_dark)
        self.assertTrue(light.hasFocus())
        QTest.keyClick(light, Qt.Key.Key_End)
        self.assertTrue(w.ui_dark)
        QTest.keyClick(dark, Qt.Key.Key_Left)
        self.assertFalse(w.ui_dark)
        QTest.keyClick(light, Qt.Key.Key_Space)
        self.assertFalse(w.ui_dark)
        dark.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(dark, Qt.Key.Key_Return)
        self.assertTrue(w.ui_dark)
        self.assertEqual(w.draft(), w.applied)

    def test_external_theme_toggle_and_theme_toggle_alias_stay_in_sync(self):
        w = self.window
        selector = self.selector()
        self.assertIs(w.findChild(QPushButton, 'themeToggle'), w.theme_button)
        self.assertIs(selector.buttons[True], w.theme_button)
        w.toggle_workspace_theme()
        self.assertFalse(w.ui_dark)
        self.assertTrue(selector.buttons[False].isChecked())
        self.assertEqual(selector.buttons[False].text(), '浅色')
        self.assertEqual(w.theme_button.text(), '深色')
        w.theme_button.click()
        self.assertTrue(w.ui_dark)
        self.assertTrue(w.theme_button.isChecked())
        self.assertEqual(w.theme_button.text(), '深色')
        w.theme_button.click()
        self.assertTrue(w.ui_dark)

    def test_selector_fits_settings_card_at_supported_widths(self):
        w = self.window
        selector = self.selector()
        for dark in (False, True):
            selector.buttons[dark].click()
            for width in (880, 1180, 1706):
                with self.subTest(dark=dark, width=width):
                    w.resize(width, 850)
                    APP.processEvents()
                    APP.processEvents()
                    viewport = w.stack.widget(3).viewport()
                    self.assertTrue(viewport.rect().contains(selector.mapTo(viewport, QPoint())))
                    self.assertTrue(viewport.rect().contains(selector.mapTo(viewport, selector.rect().bottomRight())))
                    self.assertEqual(w.stack.widget(3).horizontalScrollBar().maximum(), 0)
                    for button in selector.buttons.values():
                        self.assertTrue(button.isVisible())
                        self.assertGreaterEqual(button.height(), 28)
                        self.assertTrue(button.accessibleName())
                        self.assertFalse(button.icon().isNull())


if __name__ == '__main__':
    unittest.main()
