import unittest
from unittest.mock import patch, Mock
from pathlib import Path
import runpy
import sys
from scripts import build_release


class BuildTests(unittest.TestCase):
    def test_output_root_cli_forwards_an_isolated_candidate_directory(self):
        with patch.object(sys, 'argv', ['build_release', '--skip-installer', '--output-root', '.local/release-test']), \
             patch.object(build_release, 'build_release', return_value={}) as builder:
            build_release.main()
        self.assertEqual(builder.call_args.args[3], Path('.local/release-test'))

    def test_background_runtime_hook_skips_qt_import_without_affecting_gui(self):
        hook=Path(__file__).resolve().parents[3]/'packaging/windows/headless_runtime.py'
        self.assertTrue(hook.exists(),'Headless runtime hook missing')
        for args,skip in ((['Pointer.exe','--run'],True),(['Pointer.exe','--prepare-cursors'],True),(['Pointer.exe','--gui'],False)):
            with self.subTest(args=args):
                qt=Mock();original=qt.create_embedded_qt_conf
                utility=Mock(qt=qt)
                with patch.object(sys,'argv',args),patch.dict(sys.modules,{'_pyi_rth_utils':utility}):
                    runpy.run_path(str(hook))
                    qt.create_embedded_qt_conf('PySide6','prefix')
                    self.assertEqual(original.called,not skip)
    def test_build_path_excludes_unrelated_icu_libraries(self):
        self.assertTrue(hasattr(build_release,'clean_build_environment'),'Isolated build environment missing')
        with patch.dict(build_release.os.environ,{'PATH':r'C:\foreign\poppler\bin;C:\Windows\System32'}):
            value=build_release.clean_build_environment()
            self.assertNotIn('poppler',value['PATH'])
            self.assertIn('System32',value['PATH'])

    def test_preview_version_keeps_numeric_windows_version(self):
        self.assertTrue(hasattr(build_release,'parse_version'),'Preview version parser missing')
        self.assertEqual(build_release.parse_version('1.3.0-beta.1'),((1,3,0,0),'1.3.0-beta.1'))
        for value in ('1.3.0/../bad','1.3.0-beta.1;cmd','01.3.0','1.3.0-beta.0'):
            with self.assertRaises(ValueError):
                build_release.parse_version(value)
