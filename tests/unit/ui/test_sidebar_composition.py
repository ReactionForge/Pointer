"""Window drafts remain intact when native composition starts or falls back."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication, QMessageBox
from pointer.cursor.settings import CursorSettings
from pointer.ui.sidebar_settings import SidebarStore
from scripts.capture_material_ui import SafeMaterialWindow

APP = QApplication.instance() or QApplication([])


class FakeHost(QObject):
    ready_changed = Signal(bool)
    failed = Signal(str)

    def __init__(self):
        super().__init__()
        self.ready = True
        self.states = []
        self.starts = []
        self.closed = 0

    def start(self, hwnd):
        self.starts.append(hwnd)

    def update(self, state):
        self.states.append(state)

    def close(self):
        self.closed += 1
        self.ready = False


class SidebarCompositionTests(unittest.TestCase):
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
        self.window.select_page(3)
        self.window.show()
        APP.processEvents()
        self.window.material_active = True
        self.window._apply_reference_theme()

    def tearDown(self):
        self.window.cancel_sidebar_settings()
        self.window.discard_changes()
        self.window.close()
        self.temp.cleanup()
        for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
            getattr(self.backend, name).assert_not_called()

    def test_blur_has_its_own_live_value_save_cancel_and_restart(self):
        w = self.window
        original_cursor = w.draft()
        self.assertTrue(w.sidebar_controls.blur.isEnabled())
        w.sidebar_controls.blur.setValue(24)
        self.assertEqual(w.sidebar_appearance.blur, 24)
        self.assertTrue(self.host.states[-1]['visible'])
        self.assertEqual(self.host.states[-1]['sigma'], 24)
        w.sidebar_controls.transparency.setValue(120)
        self.assertEqual(w.sidebar_appearance.blur, 24)
        self.assertEqual(w.draft(), original_cursor)
        w.save_sidebar_settings()
        w.sidebar_controls.blur.setValue(40)
        w.cancel_sidebar_settings()
        self.assertEqual(w.sidebar_controls.blur.value(), 24)
        restarted = SafeMaterialWindow(self.backend, sidebar_store=self.store, backdrop_host=FakeHost())
        try:
            self.assertEqual(restarted.sidebar_appearance.blur, 24)
            self.assertFalse(restarted.sidebar_dirty)
        finally:
            restarted.close()

    def test_zero_blur_and_effect_off_hide_native_surface(self):
        w = self.window
        w.set_sidebar_blur(24)
        w.set_sidebar_blur(0)
        self.assertFalse(self.host.states[-1]['visible'])
        self.assertTrue(w.sidebar_transparent)
        w.set_sidebar_blur(24)
        w.set_sidebar_transparent(False)
        self.assertFalse(self.host.states[-1]['visible'])
        self.assertEqual(w.sidebar_appearance.blur, 24)

    def test_helper_failure_falls_back_without_overwriting_preferences(self):
        w = self.window
        w.set_sidebar_blur(24)
        w.save_sidebar_settings()
        saved = self.store.path.read_bytes()
        self.host.ready = False
        self.host.ready_changed.emit(False)
        self.host.failed.emit('simulated helper exit')
        self.assertFalse(w.sidebar_transparent)
        self.assertFalse(w.sidebar_controls.blur.isEnabled())
        self.assertEqual(w.sidebar_appearance.blur, 24)
        self.assertFalse(w.sidebar_dirty)
        self.assertEqual(self.store.path.read_bytes(), saved)
        self.assertTrue(w.isVisible())

    def test_policy_and_activation_hide_without_editing_saved_blur(self):
        w = self.window
        w.set_sidebar_blur(24)
        w.save_sidebar_settings()
        w.material_active = False
        w._apply_reference_theme()
        self.assertFalse(self.host.states[-1]['visible'])
        w.material_active = True
        w._apply_reference_theme()
        self.assertTrue(self.host.states[-1]['visible'])
        with patch('pointer.ui.material_workspace.transparency_policy', return_value={'supported': False}):
            w.refresh_material_policy()
        self.assertFalse(self.host.states[-1]['visible'])
        self.assertFalse(w.sidebar_dirty)
        self.assertEqual(w.sidebar_saved.blur, 24)

    def test_cancelled_close_keeps_helper_then_accept_releases_it(self):
        w = self.window
        w.set_sidebar_blur(24)
        with patch('pointer.ui.material_workspace.ask_confirmation', return_value=QMessageBox.StandardButton.No):
            self.assertFalse(w.close())
        self.assertEqual(self.host.closed, 0)
        with patch('pointer.ui.material_workspace.ask_confirmation', return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(w.close())
        self.assertEqual(self.host.closed, 1)

    def test_geometry_failure_stops_sync_before_the_fallback_reenters(self):
        w = self.window
        with patch.object(w, '_sidebar_native_rect', side_effect=OSError('client window unavailable')), \
             patch.object(w, '_apply_reference_theme', side_effect=w._sync_sidebar_backdrop):
            w._sync_sidebar_backdrop()
        self.assertEqual(self.host.closed, 1)
        self.assertIn('client window unavailable', w.composition_error)
        self.assertFalse(w.blur_available)
        self.assertTrue(w.isVisible())
