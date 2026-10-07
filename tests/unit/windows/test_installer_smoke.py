"""CI installer icon checks without installing or touching real shortcuts."""
import base64
import ctypes
import json
import ntpath
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from scripts import smoke_installer as smoke


class InstallerSmokeTests(unittest.TestCase):
    def test_install_and_upgrade_select_desktop_icon_and_check_both_shortcuts(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'VERSION').write_text('1.3.0-beta.4')
            stage = root / 'isolated'
            stage.mkdir()
            calls = []

            def run(command, **kwargs):
                calls.append(command)
                executable = Path(command[0]).name
                target = stage / 'Pointer 自定义安装'
                if executable.endswith('-setup-x64.exe'):
                    target.mkdir(exist_ok=True)
                    for name in ('Pointer.exe', 'pointer.ico', 'unins000.exe'):
                        (target / name).write_bytes(b'fixture')
                    (stage / 'install.log').write_text('mock installer')
                elif executable == 'Pointer.exe':
                    (stage / 'data/upgrade-state.json').write_text('{}')
                    Path(command[command.index('--report') + 1]).write_text('{}')
                elif executable == 'unins000.exe':
                    (target / 'Pointer.exe').unlink()
                else:
                    self.fail('Unexpected subprocess: ' + str(command))
                return subprocess.CompletedProcess(command, 0)

            with patch.object(smoke, 'ROOT', root), \
                 patch.object(smoke.tempfile, 'TemporaryDirectory') as temporary, \
                 patch.object(smoke.subprocess, 'run', side_effect=run), \
                 patch.object(smoke, 'verify_shortcuts', create=True,
                              return_value=self.records(stage / 'Pointer 自定义安装')) as verify, \
                 patch('builtins.print') as output:
                temporary.return_value.__enter__.return_value = str(stage)
                smoke.main()
            installs = [command for command in calls if command[0].endswith('-setup-x64.exe')]
            self.assertEqual(len(installs), 2)
            for command in installs:
                self.assertIn('/TASKS=desktopicon', command)
            self.assertEqual(verify.call_args_list, [unittest.mock.call(stage / 'Pointer 自定义安装',
                                                  evidence=root / '.local/reports/installer-shortcuts')] * 2)
            self.assertTrue(all(call.args[0].isascii() for call in output.call_args_list),
                            'Redirected CI stdout may use a legacy encoding')
            self.assertEqual((stage / 'data/settings.json').read_bytes(),
                             b'{"schema_version": 1, "motion": "shrink", "startup": false}')
            self.assertEqual((stage / 'Pointer 自定义安装/user-note.txt').read_text(), 'mine')
            self.assertEqual((root / '.local/reports/installer-smoke.log').read_text(), 'mock installer')

    def require_verifier(self):
        self.assertTrue(hasattr(smoke, 'verify_shortcuts'), 'Shortcut verification is missing')

    def records(self, target):
        return [{'kind': kind, 'path': str(target.parent / kind / 'Pointer.lnk'),
                 'target': str(target / 'Pointer.exe'), 'icon': str(target / 'pointer.ico') + ',0'}
                for kind in ('desktop', 'start_menu')]

    def create_target(self, target):
        target.mkdir()
        (target / 'Pointer.exe').write_bytes(b'fixture')
        (target / 'pointer.ico').write_bytes(b'fixture')

    def test_matching_shortcuts_extract_their_actual_shell_icons(self):
        self.require_verifier()
        with tempfile.TemporaryDirectory(prefix='Pointer 图标 ') as folder:
            target = Path(folder) / 'Pointer 自定义安装'
            self.create_target(target)
            records = self.records(target)
            records[0]['target'] = str(target / 'Pointer.exe').upper()
            records[0]['icon'] = '"' + str(target / 'pointer.ico') + '", 0'
            with patch.object(smoke, 'read_shortcuts', return_value=records), \
                 patch.object(smoke, 'verify_shell_icon') as extract:
                self.assertEqual(smoke.verify_shortcuts(target), records)
            self.assertEqual(extract.call_args_list,
                             [unittest.mock.call(Path(row['path']), expected_icon=target / 'pointer.ico') for row in records])

    def test_short_and_long_path_aliases_compare_by_their_resolved_files(self):
        short = Path('C:/Users/RUNNER~1/AppData/Local/Temp/Pointer 临时安装')
        long = Path('C:/Users/runneradmin/AppData/Local/Temp/Pointer 临时安装')
        aliases = {ntpath.normcase(str(root / name)): long / name
                   for root in (short, long) for name in ('Pointer.exe', 'pointer.ico')}

        def canonical(path, *args, **kwargs):
            # Deterministic 8.3 expansion, independent of host volume settings.
            return aliases[ntpath.normcase(str(path))]

        for target, linked in [(short, long), (long, short)]:
            with self.subTest(target=target, linked=linked):
                rows = self.records(linked)
                rows[0]['target'] = '"' + rows[0]['target'].upper() + '"'
                rows[0]['icon'] = '"' + str(linked / 'pointer.ico') + '",0'
                rows[1]['target'] = str(target / 'Pointer.exe')
                rows[1]['icon'] = str(target / 'pointer.ico') + ',0'
                with patch.object(Path, 'is_file', return_value=True), \
                     patch.object(Path, 'resolve', autospec=True, side_effect=canonical), \
                     patch.object(smoke, 'read_shortcuts', return_value=rows), \
                     patch.object(smoke, 'verify_shell_icon') as extract:
                    self.assertEqual(smoke.verify_shortcuts(target), rows)
                self.assertEqual(extract.call_count, 2)

    def test_stale_target_wrong_icon_or_missing_shortcut_fails_before_extraction(self):
        self.require_verifier()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'app'
            self.create_target(target)
            for field, value in [('target', str(target.parent / 'old/Pointer.exe')),
                                 ('icon', str(target / 'Pointer.exe') + ',0'),
                                 ('icon', str(target / 'pointer.ico') + ',1'),
                                 ('icon', str(target / 'pointer.ico'))]:
                with self.subTest(field=field, value=value):
                    records = self.records(target)
                    records[0][field] = value
                    with patch.object(smoke, 'read_shortcuts', return_value=records), \
                         patch.object(smoke, 'verify_shell_icon') as extract:
                        with self.assertRaises(AssertionError):
                            smoke.verify_shortcuts(target)
                        extract.assert_not_called()
            for records in [[], self.records(target)[:1], self.records(target)[:1] * 2]:
                with self.subTest(records=records), \
                     patch.object(smoke, 'read_shortcuts', return_value=records), \
                     patch.object(smoke, 'verify_shell_icon') as extract:
                    with self.assertRaises(AssertionError):
                        smoke.verify_shortcuts(target)
                    extract.assert_not_called()

    def test_shell_extraction_failure_fails_the_installer_check(self):
        self.require_verifier()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'app'
            self.create_target(target)
            with patch.object(smoke, 'read_shortcuts', return_value=self.records(target)), \
                 patch.object(smoke, 'verify_shell_icon', side_effect=AssertionError('empty Shell icon')):
                with self.assertRaisesRegex(AssertionError, 'empty Shell icon'):
                    smoke.verify_shortcuts(target)

    def test_missing_icon_file_cannot_pass_with_a_shell_fallback_icon(self):
        self.require_verifier()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / 'app'
            self.create_target(target)
            (target / 'pointer.ico').unlink()
            with patch.object(smoke, 'read_shortcuts', return_value=self.records(target)), \
                 patch.object(smoke, 'verify_shell_icon') as extract:
                with self.assertRaisesRegex(AssertionError, 'pointer.ico'):
                    smoke.verify_shortcuts(target)
                extract.assert_not_called()

    def test_shortcut_reader_uses_known_folders_and_never_saves(self):
        self.assertTrue(hasattr(smoke, 'read_shortcuts'), 'Shortcut reader is missing')
        rows = self.records(Path('C:/isolated/Pointer'))
        completed = subprocess.CompletedProcess([], 0, json.dumps(rows), '')
        metadata = {row['path']: {'target': row['target'], 'icon': row['icon']} for row in rows}
        with patch.object(smoke.subprocess, 'run', return_value=completed) as run, \
             patch.object(smoke, 'read_shortcut', side_effect=lambda path: metadata[str(path)]) as native:
            self.assertEqual(smoke.read_shortcuts(), rows)
        self.assertEqual(native.call_count, 2)
        command = run.call_args.args[0]
        script = base64.b64decode(command[-1]).decode('utf-16-le')
        self.assertIn("GetFolderPath('DesktopDirectory')", script)
        self.assertIn("GetFolderPath('Programs')", script)
        self.assertIn('Pointer\\Pointer.lnk', script)
        self.assertIn('Test-Path -LiteralPath', script)
        self.assertNotIn('WScript.Shell', script)
        self.assertNotIn('CreateShortcut(', script)
        self.assertNotIn('.Save(', script)
        self.assertEqual(run.call_args.kwargs['encoding'], 'utf-8')
        self.assertLessEqual(run.call_args.kwargs['timeout'], 30)


class ShellIconTests(unittest.TestCase):
    def native_mocks(self, draw=True, found=True, actual_rgb=(177, 31, 1), expected_rgb=None,
                     actual_alpha=255, expected_alpha=255):
        pixels = ctypes.create_string_buffer(32 * 32 * 4)

        def extract(path, attributes, info, size, flags):
            info._obj.iIcon = 7
            self.assertEqual(flags, 0x4000, 'Retrieve the actual link image list without an overlay HICON')
            return 789 if found else 0

        def bitmap(dc, header, usage, bits, section, offset):
            ctypes.cast(bits, ctypes.POINTER(ctypes.c_void_p))[0] = ctypes.addressof(pixels)
            return 222

        def render(*args):
            if draw:
                color = (expected_rgb or actual_rgb) if args[3] == 456 else actual_rgb
                alpha = expected_alpha if args[3] == 456 else actual_alpha
                pixels[:4] = bytes((*reversed(color), alpha))
            return True

        ole = SimpleNamespace(CoInitialize=Mock(return_value=0), CoUninitialize=Mock())
        shell = SimpleNamespace(SHGetFileInfoW=Mock(side_effect=extract))
        comctl = SimpleNamespace(ImageList_GetIcon=Mock(return_value=123),
                                  ImageList_Destroy=Mock())
        user = SimpleNamespace(DrawIconEx=Mock(side_effect=render), DestroyIcon=Mock(return_value=True),
                               LoadImageW=Mock(return_value=456))
        gdi = SimpleNamespace(CreateCompatibleDC=Mock(return_value=111),
                              CreateDIBSection=Mock(side_effect=bitmap),
                              SelectObject=Mock(return_value=333), GdiFlush=Mock(return_value=True),
                              DeleteObject=Mock(return_value=True), DeleteDC=Mock(return_value=True))
        return {'ole32': ole, 'shell32': shell, 'user32': user, 'gdi32': gdi, 'comctl32': comctl}

    def require_extractor(self):
        self.assertTrue(hasattr(smoke, 'verify_shell_icon'), 'Shell icon extraction is missing')

    def test_shell_icon_renders_visible_pixels_and_releases_native_resources(self):
        self.require_extractor()
        native = self.native_mocks()
        with patch.object(smoke.ctypes, 'WinDLL', side_effect=lambda name, **kw: native[name]):
            smoke.verify_shell_icon(Path('C:/isolated/desktop/Pointer.lnk'))
        native['user32'].DestroyIcon.assert_called_once_with(123)
        native['comctl32'].ImageList_GetIcon.assert_called_once_with(789, 7, 0)
        native['comctl32'].ImageList_Destroy.assert_not_called()
        native['gdi32'].DeleteObject.assert_called_once_with(222)
        native['gdi32'].DeleteDC.assert_called_once_with(111)
        self.assertEqual(native['gdi32'].SelectObject.call_args_list,
                         [unittest.mock.call(111, 222), unittest.mock.call(111, 333)])
        native['ole32'].CoUninitialize.assert_called_once()

    def test_transparent_or_missing_shell_icon_is_rejected(self):
        self.require_extractor()
        for draw, found in [(False, True), (False, False)]:
            with self.subTest(draw=draw, found=found):
                native = self.native_mocks(draw=draw, found=found)
                with patch.object(smoke.ctypes, 'WinDLL', side_effect=lambda name, **kw: native[name]):
                    with self.assertRaisesRegex(AssertionError, 'Shell icon'):
                        smoke.verify_shell_icon(Path('C:/isolated/Pointer.lnk'))
                native['ole32'].CoUninitialize.assert_called_once()
                if found:
                    native['user32'].DestroyIcon.assert_called_once_with(123)
                    native['gdi32'].DeleteObject.assert_called_once_with(222)
                else:
                    native['user32'].DestroyIcon.assert_not_called()
                    native['gdi32'].CreateCompatibleDC.assert_not_called()

    def test_render_error_releases_icon_bitmap_dc_and_com(self):
        self.require_extractor()
        native = self.native_mocks()
        native['user32'].DrawIconEx.side_effect = OSError('mock render failure')
        with patch.object(smoke.ctypes, 'WinDLL', side_effect=lambda name, **kw: native[name]):
            with self.assertRaisesRegex(OSError, 'mock render failure'):
                smoke.verify_shell_icon(Path('C:/isolated/Pointer.lnk'))
        native['user32'].DestroyIcon.assert_called_once_with(123)
        native['gdi32'].DeleteObject.assert_called_once_with(222)
        native['gdi32'].DeleteDC.assert_called_once_with(111)
        native['ole32'].CoUninitialize.assert_called_once()

    def test_preexisting_com_apartment_is_not_uninitialized(self):
        self.require_extractor()
        native = self.native_mocks()
        native['ole32'].CoInitialize.return_value = -2147417850  # RPC_E_CHANGED_MODE
        with patch.object(smoke.ctypes, 'WinDLL', side_effect=lambda name, **kw: native[name]):
            smoke.verify_shell_icon(Path('C:/isolated/Pointer.lnk'))
        native['ole32'].CoUninitialize.assert_not_called()
        native['user32'].DestroyIcon.assert_called_once_with(123)

    def test_matching_expected_icon_renders_both_handles_with_unicode_filename(self):
        native = self.native_mocks(actual_alpha=0, expected_alpha=255)
        expected = Path('C:/isolated/Pointer 中文/pointer.ico')
        with patch.object(smoke.ctypes, 'WinDLL', side_effect=lambda name, **kw: native[name]):
            smoke.verify_shell_icon(Path('C:/isolated/Pointer.lnk'), expected_icon=expected)
        native['user32'].LoadImageW.assert_called_once_with(None, str(expected), 1, 32, 32, 0x10)
        self.assertEqual([call.args[3] for call in native['user32'].DrawIconEx.call_args_list], [123, 456])
        self.assertEqual({call.args[0] for call in native['user32'].DestroyIcon.call_args_list}, {123, 456})
        self.assertEqual(native['user32'].DestroyIcon.call_count, 2)
        native['ole32'].CoUninitialize.assert_called_once()

    def test_shell_alpha_quantization_allows_two_rgb_levels_but_rejects_three(self):
        for actual, accepted in [((175, 29, 1), True), ((174, 31, 1), False)]:
            with self.subTest(actual=actual, accepted=accepted):
                native = self.native_mocks(actual_rgb=actual, expected_rgb=(177, 31, 1))
                with patch.object(smoke.ctypes, 'WinDLL', side_effect=lambda name, **kw: native[name]):
                    if accepted:
                        smoke.verify_shell_icon(Path('C:/isolated/Pointer.lnk'),
                                                expected_icon=Path('C:/isolated/pointer.ico'))
                    else:
                        with self.assertRaisesRegex(AssertionError, 'maximum RGB difference 3'):
                            smoke.verify_shell_icon(Path('C:/isolated/Pointer.lnk'),
                                                    expected_icon=Path('C:/isolated/pointer.ico'))
                self.assertEqual(native['user32'].DestroyIcon.call_count, 2)
                native['comctl32'].ImageList_Destroy.assert_not_called()

    def test_system_image_list_icon_copy_failure_is_not_accepted(self):
        native = self.native_mocks()
        native['comctl32'].ImageList_GetIcon.return_value = 0
        with patch.object(smoke.ctypes, 'WinDLL', side_effect=lambda name, **kw: native[name]):
            with self.assertRaisesRegex(AssertionError, 'Missing Shell icon'):
                smoke.verify_shell_icon(Path('C:/isolated/Pointer.lnk'),
                                        expected_icon=Path('C:/isolated/pointer.ico'))
        native['user32'].DestroyIcon.assert_not_called()
        native['user32'].LoadImageW.assert_not_called()
        native['comctl32'].ImageList_Destroy.assert_not_called()
        native['gdi32'].CreateCompatibleDC.assert_not_called()
        native['ole32'].CoUninitialize.assert_called_once()

    def test_generic_or_wrong_nonempty_artwork_fails_and_releases_both_icons(self):
        for actual in ((255, 255, 255), (0, 80, 200)):
            with self.subTest(actual=actual):
                native = self.native_mocks(actual_rgb=actual, expected_rgb=(177, 31, 1))
                with patch.object(smoke.ctypes, 'WinDLL', side_effect=lambda name, **kw: native[name]):
                    with self.assertRaisesRegex(AssertionError, 'artwork.*RGB pixels'):
                        smoke.verify_shell_icon(Path('C:/isolated/Pointer.lnk'), expected_icon=Path('C:/isolated/pointer.ico'))
                self.assertEqual({call.args[0] for call in native['user32'].DestroyIcon.call_args_list}, {123, 456})
                native['gdi32'].DeleteObject.assert_called_once_with(222)
                native['gdi32'].DeleteDC.assert_called_once_with(111)
                native['ole32'].CoUninitialize.assert_called_once()

    def test_render_exception_also_releases_the_expected_icon(self):
        for failed_handle in (123, 456):
            with self.subTest(failed_handle=failed_handle):
                native = self.native_mocks()
                original = native['user32'].DrawIconEx.side_effect

                def render(*args):
                    if args[3] == failed_handle:
                        raise OSError('mock render failure')
                    return original(*args)

                native['user32'].DrawIconEx.side_effect = render
                with patch.object(smoke.ctypes, 'WinDLL', side_effect=lambda name, **kw: native[name]):
                    with self.assertRaisesRegex(OSError, 'mock render failure'):
                        smoke.verify_shell_icon(Path('C:/isolated/Pointer.lnk'),
                                                expected_icon=Path('C:/isolated/pointer.ico'))
                self.assertEqual({call.args[0] for call in native['user32'].DestroyIcon.call_args_list}, {123, 456})
                native['gdi32'].DeleteObject.assert_called_once_with(222)
                native['gdi32'].DeleteDC.assert_called_once_with(111)
                native['ole32'].CoUninitialize.assert_called_once()

    def test_missing_expected_icon_fails_without_accepting_a_visible_shell_fallback(self):
        native = self.native_mocks()
        native['user32'].LoadImageW.return_value = 0
        with patch.object(smoke.ctypes, 'WinDLL', side_effect=lambda name, **kw: native[name]):
            with self.assertRaisesRegex(AssertionError, 'expected icon'):
                smoke.verify_shell_icon(Path('C:/isolated/Pointer.lnk'), expected_icon=Path('C:/isolated/missing.ico'))
        native['user32'].DestroyIcon.assert_called_once_with(123)
        native['ole32'].CoUninitialize.assert_called_once()


if __name__ == '__main__':
    unittest.main()
