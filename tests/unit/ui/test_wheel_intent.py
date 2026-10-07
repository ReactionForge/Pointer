import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock
from PySide6.QtCore import Qt, QPoint, QPointF, QObject, QEvent
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication, QWidget, QVBoxLayout
from PySide6.QtTest import QTest
from pointer.cursor.settings import CursorSettings
from pointer.ui.main_window import MainWindow
from pointer.ui.input_controls import PropertyScrollArea, TypedSpinBox

APP = QApplication.instance() or QApplication([])


def wheel(widget, angle=-120, pixels=0, phase=Qt.ScrollPhase.NoScrollPhase, horizontal=False, inverted=False):
    point = widget.rect().center()
    pixel = QPoint(pixels, 0) if horizontal else QPoint(0, pixels)
    delta = QPoint(angle, 0) if horizontal else QPoint(0, angle)
    event = QWheelEvent(QPointF(point), QPointF(widget.mapToGlobal(point)), pixel, delta,
                        Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier, phase, inverted)
    QApplication.sendEvent(widget, event)


class WheelIntentTests(unittest.TestCase):
    def test_forwarded_event_preserves_metadata_and_scrolls_exactly_once(self):
        combo = self.window.pages[0].family_size
        scroll = self.window.stack.widget(0)
        received = []
        class Observer(QObject):
            def eventFilter(self, watched, event):
                if event.type() == QEvent.Type.Wheel:
                    received.append((event.position(), event.globalPosition(), event.pixelDelta(),
                                     event.angleDelta(), event.phase(), event.inverted(),
                                     event.modifiers(), event.timestamp(), event.pointingDevice()))
                return False
        observer = Observer(scroll)
        scroll.viewport().installEventFilter(observer)
        point = combo.rect().center()
        global_point = QPointF(combo.mapToGlobal(point))
        event = QWheelEvent(QPointF(point), global_point, QPoint(0, -7), QPoint(0, -120),
                            Qt.MouseButton.NoButton, Qt.KeyboardModifier.ControlModifier,
                            Qt.ScrollPhase.ScrollUpdate, True)
        event.setTimestamp(1234)
        scroll.verticalScrollBar().setValue(0)
        before = self.window.draft()
        QApplication.sendEvent(combo, event)
        self.assertEqual(len(received), 1)
        expected_local = global_point - QPointF(scroll.viewport().mapToGlobal(QPoint()))
        self.assertEqual(received[0], (expected_local, global_point, QPoint(0, -7), QPoint(0, -120),
                                     Qt.ScrollPhase.ScrollUpdate, True, Qt.KeyboardModifier.ControlModifier,
                                     1234, event.pointingDevice()))
        self.assertEqual(scroll.verticalScrollBar().value(), 7)
        self.assertEqual(self.window.draft(), before)

    def test_spin_editor_wheel_scrolls_parent_but_keyboard_still_edits(self):
        scroll = PropertyScrollArea()
        body = QWidget()
        layout = QVBoxLayout(body)
        spin = TypedSpinBox()
        spin.setValue(20)
        layout.addWidget(spin)
        body.setMinimumHeight(1000)
        scroll.setWidget(body)
        scroll.resize(300, 200)
        scroll.show()
        APP.processEvents()
        wheel(spin)
        self.assertEqual(spin.value(), 20)
        self.assertGreater(scroll.verticalScrollBar().value(), 0)
        QTest.keyClick(spin, Qt.Key.Key_Up)
        self.assertEqual(spin.value(), 21)
        spin.lineEdit().selectAll()
        QTest.keyClicks(spin.lineEdit(), '35')
        QTest.keyClick(spin.lineEdit(), Qt.Key.Key_Return)
        self.assertEqual(spin.value(), 35)
        scroll.close()

    def setUp(self):
        self.backend = Mock()
        self.backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.window = MainWindow(self.backend)
        self.window.resize(880, 620)
        self.window.show()
        APP.processEvents()

    def tearDown(self):
        self.backend.apply.assert_not_called()
        self.window.discard_changes()
        self.window.close()

    def test_closed_combo_wheel_scrolls_page_without_editing_even_with_focus(self):
        combo = self.window.pages[0].family_size
        scroll = self.window.stack.widget(0)
        for focus in ('none', 'tab', 'mouse', 'elsewhere'):
            self.window.discard_changes()
            if focus == 'none':
                combo.clearFocus()
            elif focus == 'elsewhere':
                self.window.navigation[0].setFocus()
            else:
                combo.setFocus(Qt.FocusReason.TabFocusReason if focus == 'tab' else Qt.FocusReason.MouseFocusReason)
            scroll.verticalScrollBar().setValue(0)
            APP.processEvents()
            before = self.window.draft()
            wheel(combo)
            APP.processEvents()
            self.assertEqual(self.window.draft(), before, focus)
            self.assertGreater(scroll.verticalScrollBar().value(), 0, focus)

    def test_slider_wheel_scrolls_page_but_keyboard_still_edits(self):
        self.window.select_page(1)
        slider = self.window.pages[1].sliders['strength'][0]
        scroll = self.window.stack.widget(1)
        scroll.widget().setMinimumHeight(1000)
        APP.processEvents()
        slider.setFocus(Qt.FocusReason.TabFocusReason)
        before = slider.value()
        wheel(slider)
        self.assertEqual(slider.value(), before)
        self.assertGreater(scroll.verticalScrollBar().value(), 0)
        QTest.keyClick(slider, Qt.Key.Key_Right)
        self.assertEqual(slider.value(), before + 1)

    def test_pixel_delta_phases_and_horizontal_wheel_do_not_edit_values(self):
        combo = self.window.pages[0].family_size
        scroll = self.window.stack.widget(0)
        before = self.window.draft()
        scroll.verticalScrollBar().setValue(0)
        wheel(combo, angle=0, pixels=-7, phase=Qt.ScrollPhase.ScrollUpdate, inverted=True)
        self.assertEqual(self.window.draft(), before)
        self.assertEqual(scroll.verticalScrollBar().value(), 7)
        for phase in (Qt.ScrollPhase.ScrollBegin, Qt.ScrollPhase.ScrollEnd):
            wheel(combo, angle=0, pixels=0, phase=phase)
        wheel(combo, angle=0, pixels=-3, horizontal=True, phase=Qt.ScrollPhase.ScrollMomentum)
        self.assertEqual(self.window.draft(), before)

    def test_popup_scrolls_and_escape_does_not_commit_selection(self):
        combo = self.window.preview.role
        original = combo.currentIndex()
        combo.showPopup()
        view = combo.view()
        view.setFixedHeight(140)
        APP.processEvents()
        view.scrollToTop()
        wheel(view.viewport())
        APP.processEvents()
        self.assertGreater(view.verticalScrollBar().value(), 0)
        QTest.keyClick(view, Qt.Key.Key_Escape)
        APP.processEvents()
        self.assertEqual(combo.currentIndex(), original)
