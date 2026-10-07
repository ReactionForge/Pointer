"""Integrated window controls, real outer alpha corners and stable footer."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt, QPoint, QEvent, QCoreApplication
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QMessageBox
from PySide6.QtTest import QTest

from pointer.cursor.settings import CursorSettings
from scripts.capture_material_ui import SafeMaterialWindow


APP = QApplication.instance() or QApplication([])


class MaterialChromeTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.window = SafeMaterialWindow(self.backend)
        self.window.status_timer.stop()
        self.window._prewarm_timer.stop()
        self.window.preview.timer.stop()
        self.window.show()
        APP.processEvents()
        APP.processEvents()

    def tearDown(self):
        self.window.cancel_sidebar_settings()
        self.window.discard_changes()
        self.window.close()

    def test_controls_share_the_page_title_without_a_separate_top_strip(self):
        w = self.window
        self.assertTrue(w.content_widget.isAncestorOf(w.title_bar))
        self.assertTrue(w.title_bar.isAncestorOf(w.title))
        self.assertFalse(any(label.isVisible() and label.text() == 'Pointer · 安全预览'
                             for label in w.findChildren(QLabel)))
        controls = [w.title_bar.buttons[name] for name in ('关闭', '最小化', '最大化或还原')]
        centers = [button.mapTo(w, button.rect().center()) for button in controls]
        self.assertLess(centers[0].x(), centers[1].x())
        self.assertLess(centers[1].x(), centers[2].x())
        self.assertLess(abs(centers[0].y() - w.title.mapTo(w, w.title.rect().center()).y()), 12)

    def test_outer_right_corner_has_real_alpha_and_maximizing_removes_it(self):
        w = self.window
        for dark in (False, True):
            if w.ui_dark != dark:
                w.toggle_workspace_theme()
            APP.processEvents()
            image = w.grab().toImage()
            self.assertEqual(image.pixelColor(image.width()-1, image.height()-1).alpha(), 0)
            corner = [image.pixelColor(x, y).alpha()
                      for x in range(image.width()-20, image.width())
                      for y in range(image.height()-20, image.height())]
            self.assertTrue(any(0 < alpha < 255 for alpha in corner), 'Outer edge needs antialiasing')
        w.showMaximized()
        APP.processEvents()
        image = w.grab().toImage()
        self.assertEqual(image.pixelColor(image.width()-1, image.height()-1).alpha(), 255)

    def test_window_controls_follow_the_outer_edge_when_body_width_is_capped(self):
        w = self.window
        w.select_page(2)
        w.pages[2].group_tabs.setCurrentIndex(2)
        for width, body_width, right_edge in ((880, 680, 862), (1180, 980, 1156),
                                             (1360, 1160, 1336), (1706, 1240, 1682)):
            with self.subTest(width=width):
                w.resize(width, 920)
                APP.processEvents()
                APP.processEvents()
                self.assertEqual(w.content_widget.width(), body_width)
                last = w.title_bar.buttons['最大化或还原']
                self.assertEqual(last.mapTo(w, QPoint(last.width(), 0)).x(), right_edge)
                controls = list(w.title_bar.buttons.values())
                positions = [button.mapTo(w, QPoint()) for button in controls]
                self.assertLess(abs(last.mapTo(w, last.rect().center()).y()
                                    - w.title.mapTo(w, w.title.rect().center()).y()), 12)
                scroll = w.stack.widget(2)
                for button in controls:
                    self.assertLessEqual(button.mapTo(w, QPoint(0, button.height())).y(),
                                         scroll.mapTo(w, QPoint()).y())
                scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
                APP.processEvents()
                self.assertEqual([button.mapTo(w, QPoint()) for button in controls], positions)

    def test_maximized_controls_follow_the_outer_edge(self):
        w = self.window
        w.showMaximized()
        APP.processEvents()
        APP.processEvents()
        self.assertTrue(w.isMaximized())
        self.assertLessEqual(w.content_widget.width(), 1240)
        button = w.title_bar.buttons['最大化或还原']
        inset = 18 if w.width() < 1000 else 24
        self.assertEqual(button.mapTo(w, QPoint(button.width(), 0)).x(), w.width()-inset)

    def test_traffic_lights_have_colors_and_gray_inactive_state(self):
        w = self.window
        QCoreApplication.sendEvent(w, QEvent(QEvent.Type.WindowActivate))
        for name, expected in [('关闭', '#ff5f57'), ('最小化', '#febc2e'), ('最大化或还原', '#28c840')]:
            button = w.title_bar.buttons[name]
            image = button.grab().toImage()
            self.assertEqual(image.pixelColor(image.width()//2+3, image.height()//2+2).name(), expected)
            self.assertTrue(button.accessibleName())
            self.assertGreaterEqual(button.width(), 32)
        QCoreApplication.sendEvent(w, QEvent(QEvent.Type.WindowDeactivate))
        colors = [button.grab().toImage().pixelColor(19, 18).name()
                  for button in w.title_bar.buttons.values()]
        self.assertEqual(len(set(colors)), 1)

    def test_header_drag_double_click_and_keyboard_window_buttons_preserve_dispatch(self):
        w = self.window
        with patch.object(w.windowHandle(), 'startSystemMove', return_value=True) as move:
            QTest.mousePress(w.title_bar, Qt.MouseButton.LeftButton, pos=QPoint(12, 12))
            QTest.mouseRelease(w.title_bar, Qt.MouseButton.LeftButton, pos=QPoint(12, 12))
            move.assert_called_once()
        QTest.mouseDClick(w.title_bar, Qt.MouseButton.LeftButton, pos=QPoint(12, 12))
        self.assertTrue(w.isMaximized())
        QTest.keyClick(w.title_bar.buttons['最大化或还原'], Qt.Key.Key_Return)
        self.assertFalse(w.isMaximized())
        QTest.keyClick(w.title_bar.buttons['最小化'], Qt.Key.Key_Space)
        self.assertTrue(w.isMinimized())
        w.showNormal()
        w.change(size=48)
        with patch('pointer.ui.material_workspace.ask_confirmation', return_value=QMessageBox.StandardButton.No), \
             patch('pointer.ui.main_window.ask_confirmation', return_value=QMessageBox.StandardButton.No):
            QTest.keyClick(w.title_bar.buttons['关闭'], Qt.Key.Key_Space)
        self.assertTrue(w.isVisible())
        self.assertEqual(w.draft().size, 48)

    def test_footer_status_and_explanation_stay_left_and_actions_stay_right(self):
        w = self.window
        for width, height in ((880, 620), (1360, 920)):
            w.resize(width, height)
            w.select_page(2)
            w.pages[2].group_tabs.setCurrentIndex(2)
            APP.processEvents()
            APP.processEvents()
            bar = w.findChild(QFrame, 'controlBar')
            status = w.draft_label.mapTo(bar, QPoint())
            explanation = w.feedback.mapTo(bar, QPoint())
            self.assertEqual(status.x(), explanation.x())
            self.assertLess(status.y(), explanation.y())
            self.assertEqual(w.discard.text(), '取消')
            self.assertLess(explanation.x()+w.feedback.width(), w.discard.mapTo(bar, QPoint()).x())
            self.assertEqual(bar.height(), 64)
            before = bar.mapTo(w, QPoint())
            scroll = w.stack.widget(2)
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
            APP.processEvents()
            self.assertEqual(bar.mapTo(w, QPoint()), before)
            self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)
            self.assertTrue(w.apply_button.isVisible())
        for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
            getattr(self.backend, name).assert_not_called()

    def test_footer_retains_the_full_failure_message_in_its_tooltip(self):
        message = '外观保存失败：没有写入权限。请检查目标目录，然后重新保存。'
        self.window.feedback.setText(message)
        self.window.feedback.grab()
        self.assertEqual(self.window.feedback.toolTip(), message)

    def test_footer_copy_lines_up_with_the_page_title_on_each_page(self):
        w = self.window
        for width in (880, 1180, 1706):
            w.resize(width, 920)
            for page in range(4):
                with self.subTest(width=width, page=page):
                    w.select_page(page)
                    APP.processEvents()
                    APP.processEvents()
                    title_left = w.title.mapTo(w, QPoint()).x()
                    self.assertEqual(w.draft_label.mapTo(w, QPoint()).x(), title_left)
                    self.assertEqual(w.feedback.mapTo(w, QPoint()).x(), title_left)

    def test_scrolling_cards_have_space_before_the_scrollbar_hit_area(self):
        w = self.window
        w.resize(880, 620)
        for page in (0, 3):
            with self.subTest(page=page):
                w.select_page(page)
                APP.processEvents()
                APP.processEvents()
                scroll = w.stack.widget(page)
                self.assertTrue(scroll.verticalScrollBar().isVisible())
                scrollbar_left = scroll.verticalScrollBar().mapTo(w, QPoint()).x()
                cards = [frame for frame in w.pages[page].findChildren(QFrame)
                         if frame.objectName() in ('referenceGroup', 'approvedGroup')]
                self.assertTrue(cards)
                for card in cards:
                    card_right = card.mapTo(w, QPoint(card.width(), 0)).x()
                    self.assertGreaterEqual(scrollbar_left-card_right, 8)
                self.assertEqual(scroll.horizontalScrollBar().maximum(), 0)


if __name__ == '__main__':
    unittest.main()
