"""Installer-only CLI context preserves recovery intent without changing user actions."""
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from pointer import cli
from pointer.application import Application
from pointer.cursor.settings import CursorSettings


class UpgradeContextCLITests(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.backend = Mock()
        self.backend.snapshot.return_value = {'running': False, 'startup_enabled': True}
        self.backend.startup_enabled.return_value = True
        self.backend.start.return_value = {'running': True}
        self.app = Application(root/'data', root/'app', self.backend)
        self.settings = CursorSettings(startup=True)
        self.app.store.save(self.settings)
        self.handoff = self.app.data_root/'upgrade-state.json'
        self.intent = b'installer recovery intent'
        self.handoff.write_bytes(self.intent)
        self.backup = self.app.data_root/'original-cursor-settings.json'
        self.backup.write_bytes(b'first original backup')
        self.stack.enter_context(patch.object(cli, '_application', return_value=self.app))

    def run_cli(self, *arguments, marker=None):
        report = self.app.data_root/'cli-report.json'
        with patch.dict(os.environ), patch.object(cli.sys, 'stdout', io.StringIO()), \
                patch.object(cli.sys, 'stderr', io.StringIO()):
            os.environ.pop('POINTER_UPGRADE_HANDOFF', None)
            if marker is not None:
                os.environ['POINTER_UPGRADE_HANDOFF'] = marker
            result = cli.main([*arguments, '--quiet', '--report', str(report)])
        self.assertEqual(self.backup.read_bytes(), b'first original backup')
        return result, json.loads(report.read_text(encoding='utf-8'))

    def test_normal_cli_actions_invalidate_handoff_before_native_changes(self):
        for action in ('apply', 'stop', 'restore', 'tilt', 'shrink', 'reference'):
            with self.subTest(action=action):
                self.app.store.save(self.settings)
                self.handoff.write_bytes(self.intent)
                def changed(*args, **kwargs):
                    self.assertFalse(self.handoff.exists())
                with patch.object(self.backend, 'stop', side_effect=changed), \
                        patch.object(self.backend, 'restore_original', side_effect=changed):
                    code, _ = self.run_cli('--'+action)
                self.assertEqual(code, 0)
                self.assertFalse(self.handoff.exists())

    def test_matching_marker_preserves_only_internal_apply_and_is_not_inherited(self):
        def start():
            self.assertNotIn('POINTER_UPGRADE_HANDOFF', os.environ)
            self.assertEqual(self.handoff.read_bytes(), self.intent)
            return {'running': True}
        alias = self.app.data_root/'..'/'data'/'upgrade-state.json'
        with patch.object(self.backend, 'start', side_effect=start):
            code, result = self.run_cli('--apply', marker=str(alias))
        self.assertEqual(code, 0)
        self.assertTrue(result['running'])
        self.assertEqual(self.handoff.read_bytes(), self.intent)
        self.backend.set_startup.assert_not_called()
        self.assertEqual(self.run_cli('--apply')[0], 0)
        self.assertFalse(self.handoff.exists())

    def test_foreign_marker_does_not_preserve_this_app_handoff(self):
        other = self.app.data_root.parent/'other-upgrade-state.json'
        other.write_bytes(b'other intent')
        def start():
            self.assertNotIn('POINTER_UPGRADE_HANDOFF', os.environ)
            self.assertFalse(self.handoff.exists())
            return {'running': True}
        with patch.object(self.backend, 'start', side_effect=start):
            self.assertEqual(self.run_cli('--apply', marker=str(other))[0], 0)
        self.assertEqual(other.read_bytes(), b'other intent')

    def test_matching_marker_does_not_bypass_configuration_validation(self):
        self.app.store.path.write_bytes(b'broken')
        code, result = self.run_cli('--apply', marker=str(self.handoff))
        self.assertEqual(code, 1)
        self.assertIn('ValueError', result['error'])
        self.assertEqual(self.app.store.path.read_bytes(), b'broken')
        self.assertEqual(self.handoff.read_bytes(), self.intent)
        self.backend.stop.assert_not_called()
        self.backend.apply.assert_not_called()

    def test_internal_failed_apply_rolls_back_without_consuming_handoff(self):
        settings_before = self.app.store.path.read_bytes()
        self.backend.start.side_effect = RuntimeError('helper failed')
        code, result = self.run_cli('--apply', marker=str(self.handoff))
        self.assertEqual(code, 1)
        self.assertIn('helper failed', result['error'])
        self.assertEqual(self.handoff.read_bytes(), self.intent)
        self.assertEqual(self.app.store.path.read_bytes(), settings_before)
        self.assertFalse(self.app.profile_path.exists())
        self.backend.restore.assert_called_once_with(self.backend.snapshot.return_value)
        self.backend.set_startup.assert_not_called()
