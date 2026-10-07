"""Typed sidebar values commit explicitly and preserve independent drafts."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from PySide6.QtCore import Qt, QPoint, QPointF
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from pointer.cursor.settings import CursorSettings
from pointer.ui.input_controls import TypedSpinBox
from pointer.ui.sidebar_settings import SidebarStore
from scripts.capture_material_ui import SafeMaterialWindow
from tests.unit.ui.test_sidebar_composition import FakeHost

APP = QApplication.instance() or QApplication([])


class SidebarNumericTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SidebarStore(Path(self.temp.name) / 'sidebar.json')
        self.backend = Mock()
        self.backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.host = FakeHost()
        self.window = SafeMaterialWindow(self.backend, sidebar_store=self.store, backdrop_host=self.host)
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
        self.temp.cleanup()
        for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
            getattr(self.backend, name).assert_not_called()

    def type_value(self, editor, value, *, commit=True):
        self.assertIsInstance(editor, TypedSpinBox)
        editor.setFocus(Qt.FocusReason.TabFocusReason)
        editor.selectAll()
        QTest.keyClicks(editor, str(value))
        if commit:
            QTest.keyClick(editor, Qt.Key.Key_Return)

    def test_percent_commits_on_enter_and_slider_keeps_native_precision(self):
        w = self.window
        controls = w.sidebar_controls
        self.type_value(controls.transparency_value, 37, commit=False)
        self.assertEqual(w.sidebar_appearance.dark_alpha, 184)
        controls.sync()
        self.assertEqual(controls.transparency_value.text(), '37%')
        QTest.keyClick(controls.transparency_value, Qt.Key.Key_Return)
        self.assertEqual(controls.transparency.value(), 94)
        self.assertEqual(w.sidebar_appearance.dark_alpha, 161)
        w.set_sidebar_transparency(95)
        self.assertEqual(controls.transparency_value.value(), 37)
        self.assertEqual(w.sidebar_appearance.dark_alpha, 160)
        self.assertFalse(self.store.path.exists())
        self.assertEqual(w.draft(), w.applied)

    def test_blur_enter_focus_out_and_unavailable_keep_stored_value(self):
        w = self.window
        controls = w.sidebar_controls
        self.type_value(controls.blur_value, 24, commit=False)
        self.assertEqual(w.sidebar_appearance.blur, 0)
        QTest.keyClick(controls.blur_value, Qt.Key.Key_Return)
        self.assertEqual(controls.blur.value(), 24)
        self.assertEqual(self.host.states[-1]['sigma'], 24)
        self.type_value(controls.blur_value, 10, commit=False)
        self.assertEqual(w.sidebar_appearance.blur, 24)
        controls.transparency_value.setFocus(Qt.FocusReason.TabFocusReason)
        self.assertEqual(w.sidebar_appearance.blur, 10)
        self.host.ready = False
        self.host.ready_changed.emit(False)
        self.assertFalse(controls.blur_value.isEnabled())
        self.assertEqual(controls.blur_value.text(), '未启用')
        self.assertEqual(controls.blur_value.value(), 10)
        self.assertEqual(w.sidebar_appearance.blur, 10)
        self.host.ready = True
        self.host.ready_changed.emit(True)
        self.assertEqual(controls.blur_value.text(), '10')
        self.assertTrue(controls.blur_value.isEnabled())

    def test_typed_values_save_cancel_and_restart_per_theme(self):
        w = self.window
        controls = w.sidebar_controls
        self.type_value(controls.transparency_value, 55)
        self.type_value(controls.blur_value, 17)
        w.save_sidebar_settings()
        self.assertEqual(self.store.load().dark_alpha, 115)
        self.assertEqual(self.store.load().blur, 17)
        w.toggle_workspace_theme()
        self.type_value(controls.transparency_value, 100)
        self.type_value(controls.blur_value, 48)
        self.assertEqual(w.sidebar_appearance.light_alpha, 0)
        w.cancel_sidebar_settings()
        self.assertEqual(controls.transparency_value.value(), 18)
        self.assertEqual(controls.blur_value.value(), 17)
        w.toggle_workspace_theme()
        self.assertEqual(controls.transparency_value.text(), '55%')
        restarted = SafeMaterialWindow(self.backend, sidebar_store=self.store, backdrop_host=FakeHost())
        try:
            self.assertEqual(restarted.sidebar_controls.transparency_value.value(), 55)
            self.assertEqual(restarted.sidebar_controls.blur_value.value(), 17)
            self.assertFalse(restarted.sidebar_dirty)
        finally:
            restarted.close()

    def test_editor_wheel_scrolls_page_without_changing_values(self):
        w = self.window
        w.resize(880, 620)
        APP.processEvents()
        scroll = w.stack.widget(3)
        for editor in (w.sidebar_controls.transparency_value, w.sidebar_controls.blur_value):
            self.assertIsInstance(editor, TypedSpinBox)
            before = w.sidebar_appearance
            position = editor.rect().center()
            wheel = QWheelEvent(QPointF(position), QPointF(editor.mapToGlobal(position)),
                                QPoint(0, -7), QPoint(0, -120), Qt.MouseButton.NoButton,
                                Qt.KeyboardModifier.NoModifier, Qt.ScrollPhase.ScrollUpdate, False)
            old_scroll = scroll.verticalScrollBar().value()
            QApplication.sendEvent(editor, wheel)
            self.assertEqual(w.sidebar_appearance, before)
            self.assertGreater(scroll.verticalScrollBar().value(), old_scroll)


if __name__ == '__main__':
    unittest.main()
