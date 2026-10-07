"""Window drag hit regions and native-move failure keep page input intact."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt, QPoint, QPointF, QEvent, QCoreApplication
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QLabel, QWidget
from PySide6.QtTest import QTest

from pointer.cursor.settings import CursorSettings
from scripts.capture_material_ui import SafeMaterialWindow

APP = QApplication.instance() or QApplication([])


class WindowDraggingTests(unittest.TestCase):
    def setUp(self):
        self.backend = Mock()
        self.backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.window = SafeMaterialWindow(self.backend)
        self.window.status_timer.stop()
        self.window._prewarm_timer.stop()
        self.window.preview.timer.stop()
        self.window.resize(1180, 850)
        self.window.show()
        APP.processEvents()
        APP.processEvents()

    def tearDown(self):
        self.window.cancel_sidebar_settings()
        self.window.discard_changes()
        self.window.close()

    def mouse(self, kind, local, global_pos, button, buttons):
        event = QMouseEvent(kind, QPointF(local), QPointF(global_pos), button, buttons,
                            Qt.KeyboardModifier.NoModifier)
        QCoreApplication.sendEvent(self.window.material_shell, event)

    def test_brand_and_header_gaps_dispatch_native_move_but_buttons_do_not(self):
        w = self.window
        brand = w.material_sidebar.findChild(QLabel, 'referenceBrand')
        with patch.object(w.windowHandle(), 'startSystemMove', return_value=True) as move:
            for widget, point in ((brand, brand.rect().center()),
                                  (w.material_shell, QPoint(350, 12)),
                                  (w.material_shell, QPoint(350, 65)),
                                  (w.title_bar, QPoint(12, 12))):
                with self.subTest(widget=widget.objectName(), point=point):
                    move.reset_mock()
                    QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=point)
                    QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=point)
                    move.assert_called_once()
            move.reset_mock()
            QTest.mouseClick(w.title_bar.buttons['最大化或还原'], Qt.MouseButton.LeftButton)
            self.assertTrue(w.isMaximized())
            move.assert_not_called()
            w.showNormal()
            QTest.mouseClick(w.navigation[3], Qt.MouseButton.LeftButton)
            self.assertEqual(w.stack.currentIndex(), 3)
            move.assert_not_called()

    def test_native_failure_tracks_global_delta_then_release_ends_drag(self):
        w = self.window
        original, draft, appearance = w.geometry(), w.draft(), w.sidebar_appearance
        local = QPoint(350, 40)
        start = w.mapToGlobal(local)
        delta = QPoint(80, 45)
        with patch.object(w.windowHandle(), 'startSystemMove', return_value=False):
            self.mouse(QEvent.Type.MouseButtonPress, local, start,
                       Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
            self.mouse(QEvent.Type.MouseMove, local+delta, start+delta,
                       Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
            self.assertEqual(w.pos(), original.topLeft()+delta)
            self.assertEqual(w.size(), original.size())
            self.mouse(QEvent.Type.MouseButtonRelease, local, start+delta,
                       Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
            self.mouse(QEvent.Type.MouseMove, local, start+delta+QPoint(20, 20),
                       Qt.MouseButton.NoButton, Qt.MouseButton.NoButton)
            self.assertEqual(w.pos(), original.topLeft()+delta)
        self.assertEqual(w.draft(), draft)
        self.assertEqual(w.sidebar_appearance, appearance)
        for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
            getattr(self.backend, name).assert_not_called()

    def test_native_success_does_not_also_move_manually(self):
        w = self.window
        original = w.geometry()
        local = QPoint(350, 40)
        start = w.mapToGlobal(local)
        with patch.object(w.windowHandle(), 'startSystemMove', return_value=True) as native:
            self.mouse(QEvent.Type.MouseButtonPress, local, start,
                       Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
            self.mouse(QEvent.Type.MouseMove, local+QPoint(80, 45), start+QPoint(80, 45),
                       Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
            self.mouse(QEvent.Type.MouseButtonRelease, local, start+QPoint(80, 45),
                       Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
            native.assert_called_once()
        self.assertEqual(w.geometry(), original)

    def test_manual_drag_does_not_consume_another_top_level_popup_events(self):
        w = self.window
        popup = QWidget(w, Qt.WindowType.Popup)
        popup.setMouseTracking(True)
        popup.installEventFilter(w)
        self.assertIsNot(popup.window(), w)
        local = QPoint(350, 40)
        start = w.mapToGlobal(local)
        original, draft, appearance = w.geometry(), w.draft(), w.sidebar_appearance
        try:
            with patch.object(w.windowHandle(), 'startSystemMove', return_value=False):
                for kind, button, buttons in (
                        (QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton),
                        (QEvent.Type.MouseMove, Qt.MouseButton.NoButton, Qt.MouseButton.NoButton),
                        (QEvent.Type.MouseButtonRelease, Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)):
                    with self.subTest(event=kind, buttons=buttons):
                        w._end_window_drag()
                        w.setGeometry(original)
                        start = w.mapToGlobal(local)
                        self.mouse(QEvent.Type.MouseButtonPress, local, start,
                                   Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
                        event = QMouseEvent(kind, QPointF(20, 10),
                                            QPointF(start+QPoint(80, 45)), button, buttons,
                                            Qt.KeyboardModifier.NoModifier)
                        QCoreApplication.sendEvent(popup, event)
                        self.assertEqual(w.geometry(), original)
                        self.assertIsNotNone(w._manual_move_offset)
                        self.assertEqual(w.draft(), draft)
                        self.assertEqual(w.sidebar_appearance, appearance)
        finally:
            w._end_window_drag()
            popup.deleteLater()

    def test_unrelated_ungrab_and_right_release_do_not_end_the_left_drag(self):
        w = self.window
        local = QPoint(350, 40)
        start = w.mapToGlobal(local)
        with patch.object(w.windowHandle(), 'startSystemMove', return_value=False):
            for kind in (QEvent.Type.UngrabMouse, QEvent.Type.MouseButtonRelease):
                with self.subTest(event=kind):
                    self.mouse(QEvent.Type.MouseButtonPress, local, start,
                               Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
                    if kind == QEvent.Type.UngrabMouse:
                        QCoreApplication.sendEvent(w.navigation[0], QEvent(kind))
                    else:
                        self.mouse(kind, local, start,
                                   Qt.MouseButton.RightButton, Qt.MouseButton.LeftButton)
                    self.assertIsNotNone(w._manual_move_offset)
                    self.mouse(QEvent.Type.MouseButtonRelease, local, start,
                               Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
                    self.assertIsNone(w._manual_move_offset)

    def test_own_ungrab_deactivation_and_hide_end_manual_drag(self):
        w = self.window
        local = QPoint(350, 40)
        with patch.object(w.windowHandle(), 'startSystemMove', return_value=False):
            for kind in (QEvent.Type.UngrabMouse, QEvent.Type.WindowDeactivate,
                         QEvent.Type.Hide):
                with self.subTest(event=kind):
                    w.show()
                    APP.processEvents()
                    start = w.mapToGlobal(local)
                    self.mouse(QEvent.Type.MouseButtonPress, local, start,
                               Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
                    self.assertIsNotNone(w._manual_move_offset)
                    if kind == QEvent.Type.Hide:
                        w.hide()
                    else:
                        QCoreApplication.sendEvent(w, QEvent(kind))
                    self.assertIsNone(w._manual_move_offset)
                    original = w.geometry()
                    self.mouse(QEvent.Type.MouseMove, local+QPoint(80, 45),
                               start+QPoint(80, 45), Qt.MouseButton.NoButton,
                               Qt.MouseButton.LeftButton)
                    self.assertEqual(w.geometry(), original)

    def test_maximized_manual_fallback_restores_size_and_keeps_cursor_anchor(self):
        w = self.window
        normal_size = w.size()
        w.showMaximized()
        APP.processEvents()
        local = QPoint(w.width()//2, 40)
        start = w.mapToGlobal(local)
        ratio = local.x()/w.width()
        with patch.object(w.windowHandle(), 'startSystemMove', return_value=False):
            self.mouse(QEvent.Type.MouseButtonPress, local, start,
                       Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton)
            APP.processEvents()
            APP.processEvents()
            self.assertFalse(w.isMaximized())
            self.assertEqual(w.size(), normal_size)
            anchor = QPoint(round(w.width()*ratio), local.y())
            self.assertEqual(w.mapToGlobal(anchor), start)
            restored = w.pos()
            delta = QPoint(80, 45)
            self.mouse(QEvent.Type.MouseMove, anchor+delta, start+delta,
                       Qt.MouseButton.NoButton, Qt.MouseButton.LeftButton)
            self.assertEqual(w.pos(), restored+delta)
            self.mouse(QEvent.Type.MouseButtonRelease, anchor, start+delta,
                       Qt.MouseButton.LeftButton, Qt.MouseButton.NoButton)
            self.assertIsNone(w._manual_move_offset)
