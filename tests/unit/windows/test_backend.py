"""Windows transactions preserve unrelated startup choices and original backups."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class BackendTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('pointer.windows.backend'), 'Backend missing')
        from pointer.windows.backend import WindowsBackend
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.backend = WindowsBackend(Path(self.folder.name) / 'data', Path(self.folder.name) / 'app')

    def test_restore_checks_backup_before_stopping_service(self):
        with patch.object(self.backend, 'stop') as stop:
            with self.assertRaises(FileNotFoundError):
                self.backend.restore_original()
            stop.assert_not_called()

    def test_startup_matches_owned_command_and_not_any_nonempty_value(self):
        import pointer.windows.backend as module
        with patch.object(module, '_run_value', return_value={'value':'another.exe --run','type':1}), \
             patch.object(module.startup, '_startup_command', return_value='Pointer.exe --run'):
            self.assertFalse(self.backend.startup_enabled())

    def test_unchanged_run_is_not_written_during_rollback(self):
        import pointer.windows.backend as module
        snapshot = {'registry':{},'run':None,'startup_backup':None,'running':False}
        with patch.object(self.backend, 'stop'), patch.object(module.scheme, 'restore_values'), \
             patch.object(module.scheme, 'reload_cursors'), patch.object(module, '_run_value', return_value=None), \
             patch.object(module.winreg, 'CreateKeyEx') as write:
            self.backend.restore(snapshot)
            write.assert_not_called()
