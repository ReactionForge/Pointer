"""Internal prewarm prepares only a private cache and owns its child lifecycle."""
import json
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
from pointer.cursor.settings import CursorSettings
from pointer import cli


class PrewarmProcessTests(unittest.TestCase):
    def test_cli_prepare_dispatch_never_applies_or_starts_service(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            request, report = root/'draft.json', root/'report.json'
            request.write_text(json.dumps(CursorSettings().to_dict()), encoding='utf-8')
            with patch.object(cli, '_application') as application, \
                 patch.object(cli, 'dispatch') as dispatch, \
                 patch.object(cli.switcher, 'start') as start, \
                 patch.object(cli.switcher.winreg, 'OpenKey', side_effect=AssertionError('prewarm read registry')), \
                 patch.object(cli.switcher.USER32, 'SetSystemCursor', side_effect=AssertionError('prewarm changed cursor')), \
                 patch.object(cli.config, 'apply_paths') as apply:
                code = cli.main(['--prepare-cursors', '--settings-file',str(request),
                                 '--data-dir',str(root/'data'), '--report',str(report),'--quiet'])
            self.assertEqual(code, 0)
            self.assertTrue(json.loads(report.read_text(encoding='utf-8'))['ready'])
            for forbidden in (application, dispatch, start, apply):
                forbidden.assert_not_called()
            self.assertFalse((root/'data/settings.json').exists())

    def test_hidden_process_timeout_reaps_its_own_child(self):
        from pointer.windows.prewarm_process import run_hidden
        with self.assertRaises(subprocess.TimeoutExpired):
            run_hidden([sys.executable,'-c','import time; time.sleep(10)'],
                       cwd=Path.cwd(), env=None, timeout=.15)

    def test_hidden_process_can_finish_normally(self):
        from pointer.windows.prewarm_process import run_hidden
        self.assertEqual(run_hidden([sys.executable,'-c','raise SystemExit(0)'],
                                    cwd=Path.cwd(), env=None, timeout=10), 0)

    def test_normal_exit_also_reaps_remaining_descendant(self):
        from pointer.windows.prewarm_process import run_hidden, KERNEL32, _signature
        with tempfile.TemporaryDirectory() as folder:
            pid_file = Path(folder)/'owned-child.pid'
            child = f'import os,time; from pathlib import Path; Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(30)'
            launcher = f'import subprocess,sys,time; from pathlib import Path; subprocess.Popen([sys.executable,"-c",{child!r}]);\nwhile not Path({str(pid_file)!r}).exists(): time.sleep(.01)'
            began = time.monotonic()
            self.assertEqual(run_hidden([sys.executable,'-c',launcher], cwd=Path.cwd(), env=None, timeout=10), 0)
            self.assertLess(time.monotonic() - began, 12, 'Normal cleanup exceeded its timeout plus grace')
            self._assert_exited(int(pid_file.read_text()), KERNEL32, _signature)

    def _assert_exited(self, pid, kernel, signature):
        opened = signature(kernel, 'OpenProcess', [wintypes.DWORD,wintypes.BOOL,wintypes.DWORD], wintypes.HANDLE)
        handle = opened(0x100000, False, pid)
        try:
            if handle:
                self.assertEqual(kernel.WaitForSingleObject(handle, 0), 0, 'Owned descendant survived cleanup')
        finally:
            if handle:
                kernel.CloseHandle(handle)

    def test_timeout_reaps_descendant_without_touching_other_processes(self):
        from pointer.windows.prewarm_process import run_hidden, KERNEL32, _signature
        with tempfile.TemporaryDirectory() as folder:
            pid_file = Path(folder)/'owned-child.pid'
            child = f'import os,time; from pathlib import Path; Path({str(pid_file)!r}).write_text(str(os.getpid())); time.sleep(30)'
            launcher = f'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",{child!r}]); time.sleep(30)'
            began = time.monotonic()
            with self.assertRaises(subprocess.TimeoutExpired):
                run_hidden([sys.executable,'-c',launcher], cwd=Path.cwd(), env=None, timeout=2)
            self.assertLess(time.monotonic() - began, 4.5, 'Timeout cleanup exceeded its bounded grace')
            self.assertTrue(pid_file.is_file(), 'The controlled descendant must have started')
            self._assert_exited(int(pid_file.read_text()), KERNEL32, _signature)
