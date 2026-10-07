"""The local sandbox groups stay usable without changing the cursor draft."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import unittest
from unittest.mock import Mock

from PySide6.QtCore import Qt, QEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame, QTabBar, QPushButton

from pointer.ui.pages.tests import TestPage, QT_CURSOR_MAP


APP = QApplication.instance() or QApplication([])


class TestGroupTests(unittest.TestCase):
    def setUp(self):
        self.application = Mock()
        self.page = TestPage(self.application)
        self.page.resize(960, 720)
        self.page.show()
        APP.processEvents()

    def tearDown(self):
        self.page.close()

    def select_group(self, index):
        tabs = self.page.findChild(QTabBar)
        self.assertIsNotNone(tabs, 'The long sandbox needs local task navigation')
        tabs.setCurrentIndex(index)
        APP.processEvents()

    def test_keyboard_tabs_expose_one_named_task_group_at_a_time(self):
        tabs = self.page.findChild(QTabBar)
        self.assertIsNotNone(tabs, 'The long sandbox needs local task navigation')
        self.assertEqual([tabs.tabText(i) for i in range(tabs.count())],
                         ['背景适配', '点击与拖动', '输入与加载'])
        self.assertTrue(self.page.scenario('light-arrow').isVisible())
        self.assertFalse(self.page.scenario('drag').isVisible())
        tabs.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(tabs, Qt.Key.Key_Right)
        APP.processEvents()
        self.assertTrue(self.page.scenario('drag').isVisible())
        self.assertFalse(self.page.scenario('light-arrow').isVisible())
        QTest.keyClick(tabs, Qt.Key.Key_Right)
        APP.processEvents()
        self.assertTrue(self.page.scenario('wait').isVisible())
        self.assertFalse(self.page.scenario('drag').isVisible())

    def test_gray_value_tracks_keyboard_slider_input(self):
        self.page.brightness.setValue(127)
        self.page.brightness.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(self.page.brightness, Qt.Key.Key_Right)
        self.assertEqual(self.page.brightness.value(), 128)
        value = self.page.findChild(QFrame, 'grayControls')
        self.assertIsNotNone(value, 'Gray controls should form a compact local row')
        self.assertEqual(self.page.brightness_value.text(), '128 / 255')
        self.assertIn('128,128,128', self.page.gray.styleSheet())

    def test_switching_or_hiding_clears_drag_press_and_local_loading(self):
        self.select_group(1)
        drag = self.page.scenario('drag')
        QTest.mousePress(drag, Qt.MouseButton.LeftButton)
        self.assertTrue(self.page.click_state()['down'])
        self.assertTrue(drag.dragging)
        self.select_group(2)
        self.assertFalse(self.page.click_state()['down'])
        self.assertFalse(drag.dragging)
        self.page.set_wait(True, 'working')
        self.select_group(0)
        self.assertEqual(self.page.scenario('wait').property('cursorRole'), 'arrow')
        self.select_group(2)
        self.page.set_wait(True)
        self.page.button_press()
        self.page.hide()
        APP.processEvents()
        self.assertFalse(self.page.click_state()['down'])
        self.assertEqual(self.page.scenario('wait').property('cursorRole'), 'arrow')

    def test_keyboard_button_press_counts_once_and_releases_on_group_switch(self):
        self.select_group(1)
        button = next(button for button in self.page.findChildren(QPushButton)
                      if button.property('cursorRole') == 'hand')
        button.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyPress(button, Qt.Key.Key_Space)
        self.assertEqual(self.page.click_state(), {'down': True, 'presses': 1})
        QTest.keyRelease(button, Qt.Key.Key_Space)
        self.assertEqual(self.page.click_state(), {'down': False, 'presses': 1})
        QTest.mousePress(button, Qt.MouseButton.LeftButton)
        self.select_group(0)
        self.assertFalse(button.isDown())
        self.assertEqual(self.page.click_state(), {'down': False, 'presses': 2})

    def test_loading_buttons_keep_busy_and_working_local_and_leave_ends_loading(self):
        self.select_group(2)
        buttons = {button.text(): button for button in self.page.findChildren(QPushButton)}
        area = self.page.scenario('wait')
        for text, role in [('等待', 'busy'), ('后台运行', 'working'), ('结束加载', 'arrow')]:
            button = buttons[text]
            button.setFocus(Qt.FocusReason.TabFocusReason)
            QTest.keyClick(button, Qt.Key.Key_Space)
            self.assertEqual(area.property('cursorRole'), role)
        buttons['等待'].click()
        QApplication.sendEvent(area, QEvent(QEvent.Type.Leave))
        self.assertEqual(area.property('cursorRole'), 'arrow')
        self.assertEqual(self.application.mock_calls, [])

    def test_input_and_loading_reflow_without_clipping_the_loading_label(self):
        self.select_group(2)
        for width, horizontal in ((960, True), (460, False)):
            with self.subTest(width=width):
                self.page.resize(width, 900)
                APP.processEvents()
                input_box = self.page.editor.parentWidget()
                loading_box = self.page.scenario('wait').parentWidget()
                if horizontal:
                    self.assertLess(input_box.geometry().right(), loading_box.geometry().left())
                else:
                    self.assertLess(input_box.geometry().bottom(), loading_box.geometry().top())
                surface = self.page.scenario('wait')
                self.assertTrue(surface.rect().contains(surface.label.geometry()))

    def test_all_seventeen_native_roles_remain_accessible_in_loading_group(self):
        self.select_group(2)
        tiles = self.page.findChildren(QFrame, 'roleTile')
        self.assertEqual(len(tiles), 17)
        self.assertEqual({tile.property('cursorRole') for tile in tiles}, set(QT_CURSOR_MAP))
        for tile in tiles:
            self.assertTrue(tile.isVisible())
            self.assertEqual(tile.cursor().shape(), QT_CURSOR_MAP[tile.property('cursorRole')])

    def test_sandbox_interactions_never_call_the_application(self):
        self.page.brightness.setValue(24)
        self.select_group(1)
        self.page.button_press()
        self.page.button_release()
        self.select_group(2)
        self.page.editor.setFocus()
        QTest.keyClicks(self.page.editor, ' local text')
        self.page.set_wait(True)
        self.page.finish_busy()
        self.assertEqual(self.application.mock_calls, [])


if __name__ == '__main__':
    unittest.main()
