"""Precise motion and local gray controls preserve explicit draft boundaries."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from dataclasses import replace
import unittest
from unittest.mock import Mock

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionSlider, QVBoxLayout, QWidget

from pointer.cursor.settings import CursorSettings
from pointer.ui.input_controls import PropertyScrollArea, TypedSpinBox
from pointer.ui.pages.motion import MotionPage
from pointer.ui.pages.tests import TestPage
from pointer.ui.theme import initialize_fonts

APP = QApplication.instance() or QApplication([])
initialize_fonts()


def type_number(editor, value, commit=True):
    editor.setFocus(Qt.FocusReason.TabFocusReason)
    editor.selectAll()
    QTest.keyClicks(editor, str(value))
    if commit:
        QTest.keyClick(editor, Qt.Key.Key_Return)


def send_wheel(widget):
    position = widget.rect().center()
    event = QWheelEvent(QPointF(position), QPointF(widget.mapToGlobal(position)),
                        QPoint(0, -7), QPoint(0, -120), Qt.MouseButton.NoButton,
                        Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False)
    QApplication.sendEvent(widget, event)


class MotionParameterTests(unittest.TestCase):
    def setUp(self):
        self.applied = CursorSettings(style='quill', size=48, light_body='#112233',
                                      aura_glow=True, aura_color='#aabbcc', startup=True,
                                      tray_enabled=False, auto_check_update=False)
        self.draft = self.applied
        self.changes = []
        self.window = QWidget()
        self.window.ui_dark = False
        self.page = MotionPage(self.change)
        layout = QVBoxLayout(self.window)
        layout.addWidget(self.page)
        self.page.sync(self.draft)
        self.window.resize(350, 580)
        self.window.show()
        APP.processEvents()

    def change(self, _immediate=False, **fields):
        self.changes.append(fields)
        self.draft = replace(self.draft, **fields)
        self.page.sync(self.draft)

    def tearDown(self):
        self.window.close()

    def test_numbers_commit_on_enter_and_focus_out_with_exact_units(self):
        for field, number, suffix in (('strength', 37, '%'), ('press_ms', 83, ' ms'),
                                      ('release_ms', 217, ' ms')):
            with self.subTest(field=field):
                editor = self.page.editors[field]
                self.assertIsInstance(editor, TypedSpinBox)
                previous = getattr(self.draft, field)
                type_number(editor, number, commit=False)
                self.assertEqual(getattr(self.draft, field), previous)
                self.page.sync(self.draft)
                self.assertEqual(editor.text(), str(number) + suffix)
                QTest.keyClick(editor, Qt.Key.Key_Return)
                self.assertEqual(getattr(self.draft, field), number)
                self.assertEqual(self.page.sliders[field][0].value(), number)
                type_number(editor, number + 1, commit=False)
                self.page.mode.setFocus(Qt.FocusReason.TabFocusReason)
                self.assertEqual(getattr(self.draft, field), number + 1)
        self.assertEqual(self.applied.strength, 50)

    def test_slider_keyboard_updates_number_without_duplicate_value_changes(self):
        slider = self.page.sliders['strength'][0]
        editor = self.page.editors['strength']
        slider.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(slider, Qt.Key.Key_Right)
        self.assertEqual(self.draft.strength, 51)
        self.assertEqual(editor.text(), '51%')
        self.assertEqual(self.changes, [{'strength': 51}])
        editor.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(editor, Qt.Key.Key_Up)
        self.assertEqual(self.draft.strength, 52)

    def test_reset_restores_only_actual_motion_defaults_in_one_draft_change(self):
        self.change(motion='spring', strength=87, press_ms=190, release_ms=390,
                    light_outline='#445566', game_dnd=False)
        before = self.draft
        self.changes.clear()
        self.page.reset_motion.click()
        defaults = CursorSettings()
        fields = {name: getattr(defaults, name)
                  for name in ('motion', 'strength', 'press_ms', 'release_ms')}
        self.assertEqual(self.changes, [fields])
        self.assertEqual(self.draft, replace(before, **fields))
        self.assertEqual(self.applied.motion, 'tilt')
        self.assertEqual(self.applied.light_outline, '#ffffff')
        self.assertEqual(self.page.editors['strength'].text(), '50%')

    def test_off_and_retired_modes_disable_parameters_but_reset_reactivates(self):
        for mode in ('off', 'pulse', 'trail'):
            with self.subTest(mode=mode):
                self.change(motion=mode, strength=61)
                editor = self.page.editors['strength']
                self.assertEqual(editor.value(), 61)
                self.assertFalse(editor.isEnabled())
                self.assertFalse(self.page.sliders['strength'][0].isEnabled())
                self.assertIn('未启用', editor.text())
                self.page.reset_motion.click()
                self.assertTrue(editor.isEnabled())
                self.assertEqual(self.draft.motion, CursorSettings().motion)

    def test_reset_cancels_uncommitted_number_without_reviving_it_on_focus_out(self):
        editor = self.page.editors['strength']
        type_number(editor, 73, commit=False)
        self.assertEqual(self.draft.strength, 50)
        self.page.reset_motion.click()
        self.assertEqual(editor.text(), '50%')
        self.page.mode.setFocus(Qt.FocusReason.TabFocusReason)
        self.assertEqual(self.draft.strength, 50)

    def test_presets_update_numbers_and_keep_unrelated_draft_fields(self):
        original = self.draft
        for button, fields in self.page.motion_recipes:
            with self.subTest(preset=button.text()):
                button.click()
                self.assertEqual(self.draft, replace(original, **fields))
                self.assertTrue(button.isChecked())
                for field, editor in self.page.editors.items():
                    self.assertEqual(editor.value(), getattr(self.draft, field))
                self.change(**original.to_dict())

    def test_wheel_on_editor_and_slider_scrolls_once_without_editing_draft(self):
        self.page.setParent(None)
        scroll = PropertyScrollArea()
        scroll.setWidget(self.page)
        scroll.setWidgetResizable(True)
        self.page.setMinimumHeight(900)
        scroll.resize(350, 300)
        scroll.show()
        APP.processEvents()
        try:
            for widget in (self.page.sliders['strength'][0], self.page.editors['strength'],
                           self.page.editors['strength'].lineEdit()):
                scroll.verticalScrollBar().setValue(0)
                widget.setFocus(Qt.FocusReason.TabFocusReason)
                before = self.draft
                send_wheel(widget)
                self.assertEqual(self.draft, before)
                self.assertEqual(scroll.verticalScrollBar().value(), 7)
        finally:
            scroll.takeWidget().setParent(self.window)
            scroll.close()

    def test_slider_large_drag_target_and_narrow_theme_layout(self):
        slider = self.page.sliders['strength'][0]
        option = QStyleOptionSlider()
        slider.initStyleOption(option)
        handle = slider.style().subControlRect(QStyle.ComplexControl.CC_Slider, option,
                                               QStyle.SubControl.SC_SliderHandle, slider)
        self.assertGreaterEqual(slider.height(), 32)
        self.assertGreaterEqual(handle.width(), 28)
        self.assertGreaterEqual(handle.height(), 28)
        point = handle.center() - QPoint(0, 10)
        QTest.mousePress(slider, Qt.MouseButton.LeftButton, pos=point)
        self.assertTrue(slider.isSliderDown(), 'The area outside the small thumb remains draggable')
        QTest.mouseRelease(slider, Qt.MouseButton.LeftButton, pos=point)
        for dark in (False, True):
            self.window.ui_dark = dark
            self.page.sync(self.draft)
            APP.processEvents()
            for field, (slider, editor, _) in self.page.sliders.items():
                self.assertTrue(slider.parentWidget().rect().contains(slider.geometry()), field)
                self.assertTrue(editor.parentWidget().rect().contains(editor.geometry()), field)
                self.assertLess(slider.geometry().right(), editor.geometry().left())

    def test_keyboard_focus_draws_visible_feedback_in_each_theme(self):
        slider = self.page.sliders['strength'][0]
        for dark in (False, True):
            self.window.ui_dark = dark
            self.page.sync(self.draft)
            self.page.mode.setFocus(Qt.FocusReason.TabFocusReason)
            APP.processEvents()
            before = slider.grab().toImage()
            slider.setFocus(Qt.FocusReason.TabFocusReason)
            APP.processEvents()
            self.assertTrue(slider.hasFocus())
            after = slider.grab().toImage()
            self.assertNotEqual(before, after, 'Keyboard focus must be visibly distinct')


class GrayParameterTests(unittest.TestCase):
    def setUp(self):
        self.application = Mock()
        self.page = TestPage(self.application)
        self.page.resize(460, 720)
        self.page.show()
        APP.processEvents()

    def tearDown(self):
        self.page.close()
        self.assertEqual(self.application.mock_calls, [])

    def test_gray_direct_entry_slider_keyboard_and_reset_are_local(self):
        editor = self.page.brightness_value
        self.assertIsInstance(editor, TypedSpinBox)
        type_number(editor, 42)
        self.assertEqual(self.page.brightness.value(), 42)
        self.assertIn('42,42,42', self.page.gray.styleSheet())
        self.page.brightness.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(self.page.brightness, Qt.Key.Key_Right)
        self.assertEqual(editor.text(), '43 / 255')
        self.page.gray_reset.click()
        self.assertEqual(editor.text(), '128 / 255')
        self.assertEqual(self.page.brightness.value(), 128)
        self.assertIn('128,128,128', self.page.gray.styleSheet())

    def test_gray_endpoints_and_theme_changes_preserve_current_local_value(self):
        editor = self.page.brightness_value
        self.assertIsInstance(editor, TypedSpinBox)
        for value in (0, 255):
            type_number(editor, value)
            for dark in (False, True):
                self.page.set_theme(dark)
                APP.processEvents()
                self.assertEqual(editor.value(), value)
                self.assertEqual(self.page.brightness.value(), value)
                self.assertTrue(editor.parentWidget().rect().contains(editor.geometry()))

    def test_gray_reset_cancels_pending_text_and_keeps_other_test_state(self):
        editor = self.page.brightness_value
        self.assertIsInstance(editor, TypedSpinBox)
        self.page.presses = 3
        type_number(editor, 222, commit=False)
        self.page.gray_reset.click()
        self.page.group_tabs.setFocus(Qt.FocusReason.TabFocusReason)
        self.assertEqual(self.page.brightness.value(), 128)
        self.assertEqual(editor.text(), '128 / 255')
        self.assertEqual(self.page.presses, 3)

    def test_test_page_theme_also_updates_slider_track_without_a_parent_window(self):
        slider = self.page.brightness
        for dark, color in ((False, '#c9ced8'), (True, '#656b75')):
            self.page.set_theme(dark)
            APP.processEvents()
            image = slider.grab().toImage()
            self.assertEqual(image.pixelColor(slider.width() - 24, slider.height() // 2).name(), color)


if __name__ == '__main__':
    unittest.main()
