import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import tempfile
import unittest
from pathlib import Path
from dataclasses import replace
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEvent, QCoreApplication
from pointer.cursor.settings import CursorSettings
from pointer.ui.material_workspace import MaterialWindow
from pointer.ui.sidebar_settings import SidebarStore, SidebarAppearance

APP = QApplication.instance() or QApplication([])


class IterationReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = SidebarStore(Path(self.temp.name) / 'sidebar.json')
        self.store.save(SidebarAppearance(dark_alpha=160, light_alpha=140))
        self.application = Mock()
        self.settings = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.application.settings.return_value = self.settings
        self.application.backend.snapshot.return_value = {'running': False}
        self.application.runtime_status.return_value = {'running': False}
        self.window = MaterialWindow(self.application, policy={'supported': True}, sidebar_store=self.store)
        self.window.status_timer.stop(); self.window._prewarm_timer.stop()
        self.window.preview.timer.stop(); self.window.show(); APP.processEvents()

    def tearDown(self):
        self.window.cancel_sidebar_settings(); self.window._draft = self.window.applied
        self.window.close(); self.temp.cleanup()

    def test_unedited_saved_appearance_closes_without_confirmation(self):
        w = self.window
        for page in (3, 0, 1, 2, 3):
            w.select_page(page); w.toggle_workspace_theme(); w.sync()
            QCoreApplication.sendEvent(w, QEvent(QEvent.Type.WindowDeactivate))
            QCoreApplication.sendEvent(w, QEvent(QEvent.Type.WindowActivate))
            APP.processEvents()
        self.assertFalse(w.sidebar_dirty)
        with patch('pointer.ui.material_workspace.ask_confirmation') as ask:
            self.assertTrue(w.close())
        ask.assert_not_called()

    def test_sidebar_only_footer_saves_and_clean_close_never_applies_cursor(self):
        w = self.window; w.select_page(3); w.set_sidebar_transparency(105)
        self.assertTrue(w.sidebar_dirty)
        self.assertEqual(w.apply_button.text(), '保存外观')
        self.assertTrue(w.apply_button.isEnabled())
        self.assertIn('外观待保存', w.draft_label.text())
        w.apply_button.click()
        self.assertEqual(self.store.load(), w.sidebar_appearance)
        self.assertFalse(w.sidebar_dirty)
        self.application.apply.assert_not_called()
        with patch('pointer.ui.material_workspace.ask_confirmation') as ask:
            w.close()
        ask.assert_not_called()

    def test_save_failure_keeps_pending_footer_and_cursor_draft(self):
        w = self.window; w.set_sidebar_transparency(105); w.change(size=48)
        with patch.object(self.store, 'save', side_effect=OSError('test read only')):
            w.apply_button.click()
        self.assertTrue(w.sidebar_dirty)
        self.assertEqual(w.draft().size, 48)
        self.assertTrue(w.apply_button.isEnabled())
        self.assertIn('保存失败', w.feedback.text())
        self.application.apply.assert_not_called()

    def test_footer_cancel_restores_both_drafts(self):
        w = self.window; saved = w.sidebar_saved
        w.set_sidebar_transparency(105); w.change(size=48); w.discard.click()
        self.assertEqual(w.draft(), w.applied)
        self.assertEqual(w.sidebar_appearance, saved)
        self.assertFalse(w.apply_button.isEnabled())

    def test_direct_sidebar_cancel_and_return_to_saved_value_clear_footer(self):
        w = self.window; original = 255 - w.sidebar_saved.dark_alpha
        for restore in (lambda: w.sidebar_controls.cancel.click(),
                        lambda: w.set_sidebar_transparency(original)):
            w.set_sidebar_transparency(original + 20)
            self.assertEqual(w.apply_button.text(), '保存外观')
            restore()
            self.assertFalse(w.sidebar_dirty)
            self.assertFalse(w.apply_button.isEnabled())
            self.assertEqual(w.apply_button.text(), '应用更改')
            self.assertEqual(w.draft_label.text(), '无待应用更改')

    def test_sidebar_drag_does_not_restyle_all_controls(self):
        w = self.window
        with patch.object(w, 'setStyleSheet', wraps=w.setStyleSheet) as restyle:
            for value in range(60, 70):
                w.set_sidebar_transparency(value); APP.processEvents()
        restyle.assert_not_called()
        self.assertEqual(w.sidebar_appearance.dark_alpha, 186)

    def test_runtime_poll_avoids_registry_snapshot_and_reports_pause_reason(self):
        w = self.window
        self.application.backend.snapshot.side_effect = AssertionError('full snapshot forbidden in UI poll')
        self.application.runtime_status.return_value = {'running': True, 'effects_paused': True, 'pause_reason': 'fullscreen'}
        w.refresh_status()
        self.application.runtime_status.assert_called()
        self.application.backend.snapshot.assert_not_called()
        self.assertIn('全屏', w.status.text())

    def test_identical_settings_keep_animation_and_pixmap_cache(self):
        p = self.window.preview
        key = ('existing rendered frame',); sentinel = object()
        p.put_cached_pixmap(key, sentinel); p.frame = 3; motion = p.motion
        p.set_settings(p.settings)
        self.assertIs(p.get_cached_pixmap(key), sentinel)
        self.assertIs(p.motion, motion)
        self.assertEqual(p.frame, 3)

    def test_apply_draft_requests_running_engine(self):
        w = self.window; w.change(size=48); desired = w.draft()
        operations = []
        with patch.object(w, 'run_operation', side_effect=lambda operation, *args, **kwargs: operations.append(operation)):
            w.apply_draft()
        operations[0]()
        self.application.apply.assert_called_once_with(desired)

    def test_rapid_changes_keep_one_prewarm_job_and_schedule_latest(self):
        import threading
        gate = threading.Event(); started = threading.Event()
        def block(settings):
            started.set(); gate.wait(3)
        self.application.prewarm.side_effect = block
        w = self.window
        w._trigger_prewarm()
        self.assertTrue(started.wait(1))
        try:
            for value in range(55, 65):
                w.change(strength=value); w._trigger_prewarm()
            self.assertEqual(self.application.prewarm.call_count, 1)
        finally:
            gate.set()
        from PySide6.QtTest import QSignalSpy
        spy = QSignalSpy(w.prewarm_finished)
        if w._prewarm_running:
            self.assertTrue(spy.wait(2000))
        APP.processEvents()
        self.assertTrue(w._prewarm_timer.isActive())

    def test_preview_idle_and_hidden_timers_stop_but_press_and_loading_run(self):
        from PySide6.QtTest import QTest
        p = self.window.preview
        p.refresh(); self.assertFalse(p.timer.isActive())
        p.set_down(True); self.assertTrue(p.timer.isActive())
        QTest.qWait(110); self.assertGreater(p.frame, 0); self.assertFalse(p.timer.isActive())
        p.set_down(False); QTest.qWait(210)
        self.assertEqual(p.frame, 0); self.assertFalse(p.timer.isActive())
        p.role.setCurrentIndex(p.role.findData('busy')); self.assertTrue(p.timer.isActive())
        self.window.select_page(3); self.assertFalse(p.timer.isActive())

    def test_edit_during_release_never_leaves_a_pressed_frame(self):
        from PySide6.QtTest import QTest
        p = self.window.preview
        p.set_down(True); QTest.qWait(110)
        self.assertEqual(p.frame, 4)
        p.set_down(False)
        p.set_settings(replace(p.settings, strength=51))
        QTest.qWait(220)
        self.assertFalse(p.down)
        self.assertEqual(p.frame, 0)
        self.assertFalse(p.timer.isActive())

    def test_reset_defaults_keeps_service_preferences_and_requires_apply(self):
        w = self.window
        w.applied = replace(w.applied, startup=True, auto_check_update=False, tray_enabled=False, skip_update_version='2.0.0')
        w.set_draft(replace(w.applied, style='facet', strength=90, press_ms=180))
        w.reset_defaults()
        self.assertEqual(w.draft().style, CursorSettings().style)
        self.assertEqual(w.draft().strength, CursorSettings().strength)
        for name in ('startup', 'auto_check_update', 'tray_enabled', 'skip_update_version'):
            self.assertEqual(getattr(w.draft(), name), getattr(w.applied, name))
        self.application.apply.assert_not_called()
