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

    def test_runtime_status_checks_only_owned_engine_identity(self):
        import pointer.windows.backend as module
        status = {'running': False, 'last_error': 'cursor load failed'}
        with patch.object(module.engine, 'status_directory', return_value=status, create=True) as read, \
             patch.object(module.scheme, 'read_values') as registry, \
             patch.object(self.backend, 'previous_installation') as previous:
            self.assertEqual(self.backend.runtime_status(), status)
        read.assert_called_once_with(self.backend.engine_root, self.backend.data_root)
        registry.assert_not_called()
        previous.assert_not_called()

    def test_unchanged_run_is_not_written_during_rollback(self):
        import pointer.windows.backend as module
        snapshot = {'registry':{},'run':None,'startup_backup':None,'running':False}
        with patch.object(self.backend, 'stop'), patch.object(module.scheme, 'restore_values'), \
             patch.object(module.scheme, 'reload_cursors'), patch.object(module, '_run_value', return_value=None), \
             patch.object(module.winreg, 'CreateKeyEx') as write:
            self.backend.restore(snapshot)
            write.assert_not_called()

    def test_restore_relaunch_previous_root_runs_silently_with_sw_hide(self):
        import pointer.windows.backend as module
        snapshot = {'registry':{},'run':None,'startup_backup':None,'running':False,
                    'previous_root':'C:/old_pointer'}
        with patch.object(self.backend, 'stop'), patch.object(module.scheme, 'restore_values'), \
             patch.object(module.scheme, 'reload_cursors'), patch.object(module, '_run_value', return_value=None), \
             patch.object(module, 'package_files', create=True), \
             patch('pointer.windows.installation.package_files'), \
             patch.object(module.subprocess, 'Popen') as popen_mock:
            self.backend.restore(snapshot)
            popen_mock.assert_called_once()
            kwargs = popen_mock.call_args.kwargs
            self.assertEqual(kwargs['creationflags'], 0x08000000)
            self.assertEqual(kwargs['stdin'], module.subprocess.DEVNULL)
            self.assertEqual(kwargs['stdout'], module.subprocess.DEVNULL)
            self.assertEqual(kwargs['stderr'], module.subprocess.DEVNULL)
            startupinfo = kwargs.get('startupinfo')
            self.assertIsNotNone(startupinfo)
            self.assertEqual(startupinfo.wShowWindow, 0)
