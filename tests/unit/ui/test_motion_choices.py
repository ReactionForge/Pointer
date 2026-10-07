"""Motion choices use the real popup without triggering the shell resize handler."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from pointer.cursor.settings import CursorSettings
from scripts.capture_material_ui import SafeMaterialWindow


APP = QApplication.instance() or QApplication([])


class MotionChoiceTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.window = SafeMaterialWindow(self.backend)
        self.window.status_timer.stop()
        self.window._prewarm_timer.stop()
        self.window.preview.timer.stop()
        self.window.select_page(1)
        self.window.show()
        APP.processEvents()
        APP.processEvents()
        self.combo = self.window.pages[1].mode

    def tearDown(self):
        self.combo.hidePopup()
        self.window.discard_changes()
        self.window.close()
        for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
            getattr(self.backend, name).assert_not_called()

    def open_popup(self):
        QTest.mouseClick(self.combo, Qt.MouseButton.LeftButton, pos=self.combo.rect().center())
        APP.processEvents()
        popup = self.combo.view().window()
        # The offscreen screen is only 800 px wide and otherwise clamps the
        # popup to the left. Use its normal desktop position beneath the field.
        popup.move(self.combo.mapToGlobal(QPoint(0, self.combo.height())))
        APP.processEvents()
        self.assertTrue(popup.isVisible())
        return self.combo.view()

    def test_mouse_popup_choices_update_only_the_motion_draft(self):
        original = self.window.draft()
        for row, mode in ((1, 'shrink'), (2, 'spring'), (3, 'off'), (0, 'tilt')):
            with self.subTest(mode=mode):
                view = self.open_popup()
                point = view.visualRect(view.model().index(row, 0)).center()
                QTest.mouseMove(view.viewport(), point)
                QTest.mouseClick(view.viewport(), Qt.MouseButton.LeftButton, pos=point)
                APP.processEvents()
                self.assertEqual(self.combo.currentData(), mode)
                self.assertEqual(self.window.draft().motion, mode)
                self.assertFalse(view.window().isVisible())
                self.assertEqual(self.window.last_system_resize, None)
        self.assertEqual(self.window.applied, original)

    def test_popup_hover_keeps_a_choice_cursor_and_does_not_edit(self):
        original = self.window.draft()
        view = self.open_popup()
        point = view.visualRect(view.model().index(1, 0)).center()
        QTest.mouseMove(view.viewport(), point)
        APP.processEvents()
        self.assertEqual(self.combo.cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(view.viewport().cursor().shape(), Qt.CursorShape.PointingHandCursor)
        self.assertEqual(self.window.draft(), original)

    def test_keyboard_choice_commits_and_escape_cancels_popup(self):
        view = self.open_popup()
        QTest.keyClick(view, Qt.Key.Key_Down)
        QTest.keyClick(view, Qt.Key.Key_Return)
        APP.processEvents()
        self.assertEqual(self.window.draft().motion, 'shrink')
        before = self.window.draft()
        view = self.open_popup()
        QTest.keyClick(view, Qt.Key.Key_Down)
        QTest.keyClick(view, Qt.Key.Key_Escape)
        APP.processEvents()
        self.assertEqual(self.window.draft(), before)
        self.assertFalse(view.window().isVisible())
