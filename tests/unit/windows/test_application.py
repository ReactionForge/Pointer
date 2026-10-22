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

    def test_prepare_upgrade_rejects_gui_before_snapshot_or_stop(self):
        with patch('pointer.windows.gui_ipc.prepare_gui_upgrade', side_effect=RuntimeError('dirty draft')):
            with self.assertRaisesRegex(RuntimeError, 'dirty draft'):
                self.app.prepare_upgrade()
        self.backend.snapshot.assert_not_called()
        self.backend.stop.assert_not_called()

    def test_prepare_upgrade_persistence_failure_never_stops_runtime(self):
        with patch('pointer.windows.gui_ipc.prepare_gui_upgrade'), \
                patch('pointer.application._write_json', side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError, 'disk full'):
                self.app.prepare_upgrade()
        self.backend.stop.assert_not_called()
        self.backend.restore.assert_not_called()

    def test_cli_prepare_persists_original_intent_before_stop_refreshes_status(self):
        import json
        from pointer import cli
        def stop():
            state = json.loads((self.app.data_root/'upgrade-state.json').read_text(encoding='utf-8'))
            self.assertTrue(state['running'])
            self.assertEqual(state['settings'], self.old.to_dict())
            self.assertEqual(state['upgrade_install_root'], str(self.app.install_root.resolve()))
            self.backend.snapshot.return_value['running'] = False
        self.backend.stop.side_effect = stop
        with patch('pointer.windows.gui_ipc.prepare_gui_upgrade'), \
                patch('pointer.application.Application', return_value=self.app):
            self.assertEqual(cli.dispatch('prepare_upgrade'), {'ready': True, 'previously_running': True})
        state = json.loads((self.app.data_root/'upgrade-state.json').read_text(encoding='utf-8'))
        self.assertTrue(state['running'])
        self.backend.snapshot.assert_called_once()
        self.backend.set_startup.assert_not_called()

    def test_prepare_stop_failure_restores_original_state_and_removes_own_handoff(self):
        self.backend.stop.side_effect = RuntimeError('stop failed')
        with patch('pointer.windows.gui_ipc.prepare_gui_upgrade'):
            with self.assertRaisesRegex(RuntimeError, 'stop failed'):
                self.app.prepare_upgrade()
        restored = self.backend.restore.call_args.args[0]
        self.assertTrue(restored['running'])
        self.assertEqual(restored['settings'], self.old.to_dict())
        self.assertFalse((self.app.data_root/'upgrade-state.json').exists())
        self.backend.set_startup.assert_not_called()

    def test_prepare_recovery_failure_preserves_both_errors_and_handoff(self):
        original = RuntimeError('stop failed')
        self.backend.stop.side_effect = original
        self.backend.restore.side_effect = OSError('restore failed')
        with patch('pointer.windows.gui_ipc.prepare_gui_upgrade'):
            with self.assertRaisesRegex(RuntimeError, 'stop failed.*restore failed') as caught:
                self.app.prepare_upgrade()
        self.assertIs(caught.exception.__cause__, original)
        self.assertTrue((self.app.data_root/'upgrade-state.json').exists())

    def test_user_runtime_actions_invalidate_handoff_before_system_changes(self):
        path = self.app.data_root/'upgrade-state.json'
        for action in ('pause', 'resume', 'apply', 'restore'):
            with self.subTest(action=action):
                with patch('pointer.windows.gui_ipc.prepare_gui_upgrade'):
                    self.app.prepare_upgrade()
                self.assertTrue(path.exists())
                def verify_invalidated(*args, **kwargs):
                    self.assertFalse(path.exists())
                with patch.object(self.backend, 'stop', side_effect=verify_invalidated), \
                        patch.object(self.backend, 'restore_original', side_effect=verify_invalidated):
                    result = self.app.apply(self.old) if action == 'apply' else getattr(self.app, action)()
                self.assertFalse(path.exists())
                self.assertIsNone(result['last_error'])

    def test_locked_handoff_blocks_user_runtime_changes_before_side_effects(self):
        path = self.app.data_root/'upgrade-state.json'
        with patch('pointer.windows.gui_ipc.prepare_gui_upgrade'):
            self.app.prepare_upgrade()
        original = path.read_bytes()
        unlink = Path.unlink
        def reject_handoff_delete(target, *args, **kwargs):
            if target == path:
                raise PermissionError('handoff locked')
            return unlink(target, *args, **kwargs)
        for action in ('pause', 'resume', 'apply', 'restore'):
            with self.subTest(action=action):
                self.backend.reset_mock()
                with patch.object(Path, 'unlink', reject_handoff_delete):
                    with self.assertRaisesRegex(PermissionError, 'handoff locked'):
                        if action == 'apply':
                            self.app.apply(self.old)
                        else:
                            getattr(self.app, action)()
                self.backend.stop.assert_not_called()
                self.backend.start.assert_not_called()
                self.backend.apply.assert_not_called()
                self.backend.restore_original.assert_not_called()
                self.assertEqual(path.read_bytes(), original)

    def test_invalid_configuration_keeps_handoff_and_runtime_untouched(self):
        path = self.app.data_root/'upgrade-state.json'
        with patch('pointer.windows.gui_ipc.prepare_gui_upgrade'):
            self.app.prepare_upgrade()
        original = path.read_bytes()
        self.app.store.path.write_bytes(b'broken')
        for action in ('pause', 'resume', 'apply', 'restore'):
            with self.subTest(action=action):
                self.backend.reset_mock()
                with self.assertRaises(ValueError):
                    if action == 'apply':
                        self.app.apply(self.old)
                    else:
                        getattr(self.app, action)()
                self.assertEqual(path.read_bytes(), original)
                self.backend.stop.assert_not_called()
                self.backend.restore_original.assert_not_called()

    def test_failed_user_apply_does_not_restore_superseded_upgrade_intent(self):
        with patch('pointer.windows.gui_ipc.prepare_gui_upgrade'):
            self.app.prepare_upgrade()
        self.backend.snapshot.return_value = {'running': False, 'startup_enabled': True}
        self.backend.start.side_effect = RuntimeError('helper failed')
        with self.assertRaisesRegex(RuntimeError, 'helper failed'):
            self.app.apply(self.old)
        self.assertFalse((self.app.data_root/'upgrade-state.json').exists())
        self.backend.restore.assert_called_once_with(self.backend.snapshot.return_value)

    def test_prewarm_generates_and_caches_bundle_without_starting_or_stopping_service(self):
        bundle = self.app.prewarm(self.old)
        self.assertIsNotNone(bundle)
        self.backend.start.assert_not_called()
        self.backend.stop.assert_not_called()
        self.backend.apply.assert_not_called()
