"""Configuration transactions persist real files while mocking only Windows."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from pointer.cursor.settings import CursorSettings


class ApplicationTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('pointer.application'), 'Application API missing')
        from pointer.application import Application
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = Path(self.folder.name)
        self.backend = Mock()
        self.backend.snapshot.return_value = {'running': True, 'startup_enabled': True}
        self.backend.startup_enabled.return_value = True
        self.backend.start.return_value = {'running': True, 'pid': 123}
        self.app = Application(root / 'data', root / 'app', self.backend)
        self.old = CursorSettings(motion='shrink', startup=True)
        self.app.store.save(self.old)

    def test_failed_start_restores_settings_profile_and_original_backup(self):
        before = self.app.store.path.read_bytes()
        backup = self.app.store.root / 'original-cursor-settings.json'
        backup.write_bytes(b'original backup bytes')
        self.backend.start.side_effect = RuntimeError('not ready')
        with self.assertRaisesRegex(RuntimeError, 'not ready'):
            self.app.apply(replace(self.old, motion='tilt'))
        self.assertEqual(self.app.store.path.read_bytes(), before)
        self.assertFalse(self.app.profile_path.exists())
        self.assertEqual(backup.read_bytes(), b'original backup bytes')
        self.backend.restore.assert_called_once()
        self.backend.set_startup.assert_not_called()

    def test_successful_apply_persists_selection_without_rewriting_startup(self):
        desired = replace(self.old, motion='tilt', release_ms=250)
        result = self.app.apply(desired)
        self.assertTrue(result['running'])
        self.assertEqual(self.app.store.load(), desired)
        self.assertTrue(self.app.profile_path.exists())
        self.backend.set_startup.assert_not_called()

    def test_pause_does_not_change_startup_or_preferences(self):
        before = self.app.store.path.read_bytes()
        self.app.pause()
        self.assertEqual(self.app.store.path.read_bytes(), before)
        self.backend.stop.assert_called_once()
        self.backend.set_startup.assert_not_called()

    def test_explicit_startup_toggle_updates_only_changed_state(self):
        self.app.set_startup(True)
        self.backend.set_startup.assert_not_called()
        self.app.set_startup(False)
        self.backend.set_startup.assert_called_once_with(False)
        self.assertFalse(self.app.store.load().startup)

    def test_failed_startup_toggle_preserves_preferences(self):
        before = self.app.store.path.read_bytes()
        self.backend.set_startup.side_effect = PermissionError('denied')
        with self.assertRaises(PermissionError):
            self.app.set_startup(False)
        self.assertEqual(self.app.store.path.read_bytes(), before)

    def test_failed_preference_save_rolls_back_changed_startup(self):
        with patch.object(self.app.store, 'save', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.app.set_startup(False)
        self.backend.restore.assert_called_once_with(self.backend.snapshot.return_value)

    def test_restore_keeps_custom_preferences_and_disables_startup(self):
        self.app.restore()
        self.backend.restore_original.assert_called_once()
        self.assertEqual(self.app.store.load().motion, self.old.motion)
        self.assertFalse(self.app.store.load().startup)

    def test_restore_failure_does_not_report_success_or_delete_backup(self):
        self.backend.restore_original.side_effect = RuntimeError('backup damaged')
        before = self.app.store.path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'backup damaged'):
            self.app.restore()
        self.assertEqual(self.app.store.path.read_bytes(), before)

    def test_failed_save_after_restore_rolls_back_system_choice(self):
        with patch.object(self.app.store,'save',side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError,'disk full'):
                self.app.restore()
        self.backend.restore.assert_called_once_with(self.backend.snapshot.return_value)

    def test_corrupt_configuration_is_not_overwritten_by_pause(self):
        self.app.store.path.write_bytes(b'broken')
        with self.assertRaises(ValueError):
            self.app.pause()
        self.assertEqual(self.app.store.path.read_bytes(), b'broken')
        self.backend.stop.assert_not_called()

    def test_apply_preserves_existing_damaged_configuration_before_side_effects(self):
        for damaged in (b'broken', b'{"schema_version":99}', b' '*65537):
            with self.subTest(damaged=damaged[:30]):
                self.app.store.path.write_bytes(damaged)
                with self.assertRaises(ValueError):
                    self.app.apply(CursorSettings())
                self.assertEqual(self.app.store.path.read_bytes(),damaged)
                self.backend.stop.assert_not_called()
