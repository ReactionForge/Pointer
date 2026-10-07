"""Sidebar preview, explicit save/cancel and independent restart persistence."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from PySide6.QtCore import Qt, QEvent, QCoreApplication
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtTest import QTest
from pointer.cursor.settings import CursorSettings
from pointer.ui.sidebar_settings import SidebarAppearance, SidebarStore
from scripts.capture_material_ui import SafeMaterialWindow

APP = QApplication.instance() or QApplication([])


class SidebarPreferencesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SidebarStore(Path(self.temp.name) / 'sidebar.json')
        self.backend = Mock()
        self.backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.window = SafeMaterialWindow(self.backend, sidebar_store=self.store)
        self.window.status_timer.stop()
        self.window._prewarm_timer.stop()
        self.window.select_page(3)
        self.window.show()
        APP.processEvents()

    def tearDown(self):
        self.window.cancel_sidebar_settings()
        self.window.discard_changes()
        self.window.close()
        self.temp.cleanup()

    def test_controls_moved_to_settings_live_preview_cancel_save_restart(self):
        w = self.window
        self.assertIs(w.alpha_toggle.window(), w)
        self.assertFalse(w.title_bar.isAncestorOf(w.alpha_toggle))
        self.assertTrue(w.pages[3].isAncestorOf(w.alpha_toggle))
        original = w.draft()
        w.alpha_toggle.setChecked(False)
        self.assertFalse(w.sidebar_transparent)
        self.assertTrue(w.sidebar_dirty)
        self.assertFalse(self.store.path.exists())
        self.assertEqual(w.draft(), original)
        w.cancel_sidebar_settings()
        self.assertTrue(w.sidebar_transparent)
        self.assertFalse(w.sidebar_dirty)
        w.sidebar_controls.transparency.setValue(100)
        self.assertEqual(w.sidebar_appearance.dark_alpha, 155)
        w.save_sidebar_settings()
        self.assertFalse(w.sidebar_dirty)
        restarted = SafeMaterialWindow(self.backend, sidebar_store=self.store)
        try:
            self.assertEqual(restarted.sidebar_appearance.dark_alpha, 155)
            self.assertTrue(restarted.sidebar_transparent)
        finally:
            restarted.close()
        self.backend.apply.assert_not_called()

    def test_unavailable_blur_cannot_masquerade_as_alpha(self):
        controls = self.window.sidebar_controls
        self.assertFalse(controls.blur.isEnabled())
        self.assertIn('未', controls.blur_value.text())
        before = self.window.sidebar_appearance.blur
        controls.transparency.setValue(120)
        self.assertEqual(self.window.sidebar_appearance.blur, before)

    def test_keyboard_changes_and_wheel_does_not_change_alpha(self):
        control = self.window.sidebar_controls.transparency
        control.setFocus(Qt.FocusReason.TabFocusReason)
        before = control.value()
        QTest.keyClick(control, Qt.Key.Key_Right)
        self.assertGreater(control.value(), before)
        self.assertEqual(self.window.draft(), self.window.applied)

    def test_close_confirmation_continues_editing_then_discards(self):
        w = self.window
        w.alpha_toggle.setChecked(False)
        with patch('pointer.ui.material_workspace.ask_confirmation', return_value=QMessageBox.StandardButton.No):
            self.assertFalse(w.close())
        self.assertTrue(w.isVisible())
        self.assertTrue(w.sidebar_dirty)
        with patch('pointer.ui.material_workspace.ask_confirmation', return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(w.close())
        self.assertFalse(self.store.path.exists())

    def test_fallback_preserves_saved_choice_without_system_writes(self):
        self.store.save(SidebarAppearance(enabled=True, dark_alpha=150))
        w = SafeMaterialWindow(self.backend, sidebar_store=self.store,
            policy={'supported': False, 'high_contrast': True, 'reason': 'high contrast'})
        try:
            self.assertFalse(w.sidebar_transparent)
            self.assertTrue(w.sidebar_appearance.enabled)
            self.assertFalse(w.alpha_toggle.isEnabled())
            w.show()
            QCoreApplication.sendEvent(w, QEvent(QEvent.Type.WindowActivate))
            APP.processEvents()
            self.assertEqual(w.grab().toImage().pixelColor(50, 400).alpha(), 255)
            self.assertTrue(self.store.load().enabled)
        finally:
            w.close()
        for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
            getattr(self.backend, name).assert_not_called()

    def test_failed_save_keeps_preview_and_pending_choice(self):
        w = self.window
        w.alpha_toggle.setChecked(False)
        with patch.object(self.store, 'save', side_effect=OSError('read-only test')):
            w.save_sidebar_settings()
        self.assertTrue(w.sidebar_dirty)
        self.assertFalse(w.sidebar_transparent)
        self.assertIn('保存失败', w.sidebar_controls.status.text())

    def test_live_system_policy_change_falls_back_and_restores_saved_choice(self):
        w = self.window
        fallback = {'supported': False, 'high_contrast': True, 'reason': 'simulated system change'}
        with patch('pointer.ui.material_workspace.transparency_policy', return_value=fallback):
            w.refresh_material_policy()
            self.assertFalse(w.sidebar_transparent)
            self.assertFalse(w.alpha_toggle.isEnabled())
            self.assertTrue(w.sidebar_appearance.enabled)
        with patch('pointer.ui.material_workspace.transparency_policy', return_value={'supported': True}):
            w.refresh_material_policy()
            self.assertTrue(w.sidebar_transparent)
            self.assertTrue(w.alpha_toggle.isEnabled())
        self.assertFalse(w.sidebar_dirty)

    def test_corrupt_or_invalid_store_has_safe_defaults(self):
        self.store.path.write_text('{broken', encoding='utf8')
        self.assertEqual(self.store.load(), SidebarAppearance())

    def test_both_pending_drafts_survive_cancelled_close_with_single_confirmation(self):
        w = self.window
        w.alpha_toggle.setChecked(False)
        w.change(size=48)
        appearance = w.sidebar_appearance
        draft = w.draft()
        with patch('pointer.ui.material_workspace.ask_confirmation', return_value=QMessageBox.StandardButton.No) as confirm:
            self.assertFalse(w.close())
        confirm.assert_called_once()
        self.assertEqual(w.sidebar_appearance, appearance)
        self.assertEqual(w.draft(), draft)

    def test_capture_without_store_cannot_claim_saved_restart(self):
        w = SafeMaterialWindow(self.backend)
        try:
            w.set_sidebar_transparent(False)
            w.save_sidebar_settings()
            self.assertTrue(w.sidebar_dirty)
            self.assertFalse(w.sidebar_controls.save.isEnabled())
            self.assertIn('不保存', w.sidebar_controls.status.text())
        finally:
            w.cancel_sidebar_settings()
            w.close()
        self.store.path.write_text('{"enabled": "yes", "dark_alpha": -1}', encoding='utf8')
        self.assertEqual(self.store.load(), SidebarAppearance())
