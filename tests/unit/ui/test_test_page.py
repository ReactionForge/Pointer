import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import importlib.util
import unittest
from unittest.mock import Mock
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFocusEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

QT_APP = QApplication.instance() or QApplication([])


class TestPageTests(unittest.TestCase):
    def test_focus_loss_clears_pressed_state(self):
        self.assertIsNotNone(importlib.util.find_spec('pointer.ui'), 'Test page missing')
        from pointer.ui.pages.tests import TestPage
        page = TestPage(Mock())
        surface = page.scenario('light-arrow')
        QTest.mousePress(surface, Qt.MouseButton.LeftButton)
        self.assertTrue(page.click_state()['down'])
        QApplication.sendEvent(surface, QFocusEvent(QEvent.Type.FocusOut))
        self.assertFalse(page.click_state()['down'])
        page.close()

    def test_wait_is_local_and_leaving_resets_role(self):
        self.assertIsNotNone(importlib.util.find_spec('pointer.ui'), 'Test page missing')
        from pointer.ui.pages.tests import TestPage
        page = TestPage(Mock())
        area = page.scenario('wait')
        page.set_wait(True)
        self.assertEqual(area.property('cursorRole'), 'busy')
        QApplication.sendEvent(area, QEvent(QEvent.Type.Leave))
        self.assertEqual(area.property('cursorRole'), 'arrow')
        page.close()
