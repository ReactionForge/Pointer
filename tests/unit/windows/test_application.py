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

    def test_default_apply_starts_paused_service_and_preserves_original_backup(self):
        self.backend.snapshot.return_value = {'running': False, 'startup_enabled': True}
        backup = self.app.store.root / 'original-cursor-settings.json'
        backup.write_bytes(b'original backup bytes')
        result = self.app.apply(replace(self.old, motion='tilt'))
        self.assertTrue(result['running'])
        self.backend.start.assert_called_once()
        self.backend.set_startup.assert_not_called()
        self.assertEqual(backup.read_bytes(), b'original backup bytes')

    def test_snapshot_preserves_background_error(self):
        self.backend.snapshot.return_value = {'running': False, 'last_error': 'cursor load failed'}
        self.assertEqual(self.app.snapshot()['last_error'], 'cursor load failed')

    def test_runtime_status_does_not_load_preferences_or_transaction_snapshot(self):
        status = {'running': False, 'starting': False, 'last_error': 'cursor load failed'}
        self.backend.runtime_status.return_value = status
        with patch.object(self.app, 'settings') as settings:
            self.assertEqual(self.app.runtime_status(), status)
        settings.assert_not_called()
        self.backend.snapshot.assert_not_called()

    def test_isolated_prewarm_sends_validated_draft_and_explicit_paths(self):
        import json
        desired = replace(self.old, light_body='#123456')
        # Exercise equivalent directory aliases even when TEMP has no short-name alias.
        self.app.data_root = self.app.data_root / '..' / self.app.data_root.name
        self.app.install_root = self.app.install_root / '..' / self.app.install_root.name
        requests = []
        def run(command, **kwargs):
            requests.append((command, kwargs))
            request = Path(command[command.index('--settings-file') + 1])
            report = Path(command[command.index('--report') + 1])
            self.assertEqual(json.loads(request.read_text(encoding='utf-8')), desired.to_dict())
            report.write_text(json.dumps({'exit_code':0, 'ready':True, 'key':'test', 'size':32}), encoding='utf-8')
            return 0
        with patch('pointer.windows.prewarm_process.run_hidden', side_effect=run), \
             patch.object(self.app, 'settings') as load:
            self.assertTrue(self.app.prewarm_isolated(desired)['ready'])
        load.assert_not_called()
        self.backend.apply.assert_not_called()
        self.backend.start.assert_not_called()
        command, kwargs = requests[0]
        self.assertIn('--prepare-cursors', command)
        self.assertEqual(Path(command[command.index('--data-dir') + 1]).resolve(), self.app.data_root.resolve())
        self.assertEqual(Path(command[command.index('--install-dir') + 1]).resolve(), self.app.install_root.resolve())
        self.assertGreater(kwargs['timeout'], 0)
        self.assertFalse(list(self.app.data_root.glob('.prewarm-*')))

    def test_isolated_prewarm_propagates_child_failure_and_cleans_request(self):
        def run(command, **kwargs):
            report = Path(command[command.index('--report') + 1])
            report.write_text('{"exit_code":1,"error":"resource encoding failed"}', encoding='utf-8')
            return 1
        with patch('pointer.windows.prewarm_process.run_hidden', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'resource encoding failed'):
                self.app.prewarm_isolated(self.old)
        self.assertFalse(list(self.app.data_root.glob('.prewarm-*')))

    def test_gui_apply_preserves_paused_runtime_and_original_backup(self):
        self.backend.snapshot.return_value = {'running': False, 'startup_enabled': True}
        backup = self.app.store.root / 'original-cursor-settings.json'
        backup.write_bytes(b'original backup bytes')
        desired = replace(self.old, light_outline='#123456')
        result = self.app.apply(desired, preserve_runtime=True)
        self.assertFalse(result['running'])
        self.assertEqual(self.app.store.load(), desired)
        self.assertEqual(backup.read_bytes(), b'original backup bytes')
        self.backend.start.assert_not_called()
        self.backend.set_startup.assert_not_called()

    def test_gui_apply_keeps_a_running_service_running(self):
        result = self.app.apply(replace(self.old, light_outline='#123456'), preserve_runtime=True)
        self.assertTrue(result['running'])
        self.backend.start.assert_called_once()

    def test_paused_apply_failure_rolls_back_without_starting_service(self):
        self.backend.snapshot.return_value = {'running': False, 'startup_enabled': True}
        self.backend.apply.side_effect = RuntimeError('not ready')
        before = self.app.store.path.read_bytes()
        with self.assertRaisesRegex(RuntimeError, 'not ready'):
            self.app.apply(replace(self.old, light_outline='#123456'), preserve_runtime=True)
        self.assertEqual(self.app.store.path.read_bytes(), before)
        self.backend.start.assert_not_called()
        self.backend.restore.assert_called_once_with(self.backend.snapshot.return_value)

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

    def test_prewarm_generates_and_caches_bundle_without_starting_or_stopping_service(self):
        bundle = self.app.prewarm(self.old)
        self.assertIsNotNone(bundle)
        self.backend.start.assert_not_called()
        self.backend.stop.assert_not_called()
        self.backend.apply.assert_not_called()
