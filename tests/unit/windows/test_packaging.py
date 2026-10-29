"""Exercise backup preservation and damaged-package rejection without changing Windows."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import runpy
import subprocess
import sys
import os
import winreg
from contextlib import ExitStack
from unittest.mock import patch

from pointer.windows import scheme as config
from pointer import cli as app
from pointer.windows import installation
from pointer.windows import startup as startup_module


class PackageTests(unittest.TestCase):
    def test_login_startup_reapplies_saved_cursor_scheme_before_helper(self):
        with patch("pointer.windows.engine._helper_command",
                   return_value=[r"C:\Program Files\Pointer\Pointer.exe", "--run"]):
            command = startup_module._startup_command()
        self.assertEqual(command, subprocess.list2cmdline(
            [r"C:\Program Files\Pointer\Pointer.exe", "--apply", "--quiet"]))

    def test_reapplying_preserves_startup_registration(self):
        from pointer.application import Application
        from pointer.cursor.settings import CursorSettings
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as folder:
            backend=Mock()
            backend.startup_enabled.return_value=True
            backend.start.return_value={'running':True}
            application=Application(Path(folder)/'data',Path(folder)/'app',backend)
            application.store.save(CursorSettings(startup=True))
            with patch.object(app,'_application',return_value=application):
                self.assertTrue(app.apply_theme()['startup_enabled'])
            backend.set_startup.assert_not_called()

    def test_identical_startup_entry_is_never_rewritten(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            startup = Path(folder) / "startup.json"
            startup.write_bytes(b'{"previous": null, "installed_command": "unchanged"}')
            original = startup.read_bytes()
            stack.enter_context(patch.object(startup_module, "STARTUP_BACKUP", startup))
            stack.enter_context(patch.object(startup_module, "_startup_command", return_value="unchanged"))
            stack.enter_context(patch.object(winreg, "CreateKeyEx"))
            stack.enter_context(patch.object(winreg, "QueryValueEx", return_value=("unchanged", winreg.REG_SZ)))
            write = stack.enter_context(patch.object(winreg, "SetValueEx"))
            delete = stack.enter_context(patch.object(winreg, "DeleteValue"))
            backup = stack.enter_context(patch.object(startup_module, "_atomic_json"))
            for _ in range(5):
                self.assertFalse(startup_module.enable_startup()["changed"])
            write.assert_not_called()
            delete.assert_not_called()
            backup.assert_not_called()
            self.assertEqual(startup.read_bytes(), original)

    def test_failed_upgrade_preparation_never_deletes_or_sets_unchanged_startup(self):
        from pointer.application import Application
        from pointer.cursor.settings import CursorSettings
        from pointer.windows import backend as boundary
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            data, target = Path(folder)/'data', Path(folder)/'app'
            data.mkdir()
            original = data/'original-cursor-settings.json'
            original.write_bytes(b'original cursor backup')
            startup = data/boundary.startup.STARTUP_BACKUP.name
            startup.write_bytes(b'original startup backup')
            backend = boundary.WindowsBackend(data, target)
            stack.enter_context(patch('pointer.windows.gui_ipc.prepare_gui_upgrade'))
            stack.enter_context(patch.object(backend, 'startup_enabled', return_value=True))
            stack.enter_context(patch.object(backend, 'previous_installation', return_value=None))
            stack.enter_context(patch.object(backend, 'runtime_status', return_value={}))
            stack.enter_context(patch.object(backend, 'stop', side_effect=[RuntimeError('stop failed'), None]))
            start = stack.enter_context(patch.object(backend, 'start', return_value={'running': True}))
            stack.enter_context(patch.object(boundary.engine, 'running_directory', return_value=True))
            stack.enter_context(patch.object(boundary.scheme, 'read_values', return_value={}))
            stack.enter_context(patch.object(boundary.scheme, 'restore_values'))
            stack.enter_context(patch.object(boundary.scheme, 'reload_cursors'))
            stack.enter_context(patch.object(boundary, '_run_value', return_value={'value': 'unchanged', 'type': winreg.REG_SZ}))
            write = stack.enter_context(patch.object(winreg, 'SetValueEx'))
            delete = stack.enter_context(patch.object(winreg, 'DeleteValue'))
            application = Application(data, target, backend)
            application.store.save(CursorSettings(startup=True))
            with self.assertRaisesRegex(RuntimeError, 'stop failed'):
                application.prepare_upgrade()
            start.assert_called_once()
            write.assert_not_called()
            delete.assert_not_called()
            self.assertEqual(original.read_bytes(), b'original cursor backup')
            self.assertEqual(startup.read_bytes(), b'original startup backup')

    def test_startup_upgrade_keeps_original_backup(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            startup = Path(folder) / "startup.json"
            startup.write_text(json.dumps({"value_name": startup_module.RUN_VALUE,
                                          "previous": None, "installed_command": "old path"}))
            stack.enter_context(patch.object(startup_module, "STARTUP_BACKUP", startup))
            stack.enter_context(patch.object(startup_module, "_startup_command", return_value="new path"))
            stack.enter_context(patch.object(winreg, "CreateKeyEx"))
            stack.enter_context(patch.object(winreg, "QueryValueEx", return_value=("old path", winreg.REG_SZ)))
            write = stack.enter_context(patch.object(winreg, "SetValueEx"))
            self.assertTrue(startup_module.enable_startup()["changed"])
            write.assert_called_once()
            data = json.loads(startup.read_text())
            self.assertIsNone(data["previous"])
            self.assertEqual(data["installed_command"], "new path")

    def test_upgrade_cleanup_preserves_changed_and_unowned_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = root / "legacy" / "old.cur"
            old.parent.mkdir()
            old.write_bytes(b"old cursor")
            changed = root / "custom.cur"
            changed.write_bytes(b"user change")
            unowned = root / "notes.txt"
            unowned.write_text("user notes")
            previous = {"legacy/old.cur": hashlib.sha256(old.read_bytes()).hexdigest(),
                        "custom.cur": hashlib.sha256(b"original cursor").hexdigest()}
            installation.remove_obsolete_files(previous, {}, root)
            self.assertFalse(old.parent.exists())
            self.assertEqual(changed.read_bytes(), b"user change")
            self.assertEqual(unowned.read_text(), "user notes")

    def test_source_entrypoint_works_without_site_packages_from_another_directory(self):
        repository = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory(prefix="Pointer 中文 ") as folder:
            report = Path(folder) / "diagnostics.json"
            process = subprocess.run([sys.executable, "-S", str(repository / "packaging" / "windows" / "entrypoint.py"),
                                      "--diagnose", "--quiet", "--report", str(report)],
                                     cwd=folder, capture_output=True, timeout=15)
            self.assertEqual(process.returncode, 0, process.stderr.decode(errors="replace"))
            result = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(result["cursor_resources"], 34)
            self.assertEqual(result["animated_resources"], 4)
            self.assertEqual(result["click_resources"], 32)

    def test_installed_data_survives_host_appdata_redirection(self):
        with tempfile.TemporaryDirectory() as folder:
            local = Path(folder)
            installed = local / "Packages" / "Host" / "LocalCache" / "Local" / "Pointer" / "app"
            installed.mkdir(parents=True)
            executable = installed / "Pointer.exe"
            executable.touch()
            with patch.object(app.sys, "frozen", True, create=True), \
                 patch.object(app.sys, "executable", str(executable)), \
                 patch.dict(os.environ, {"LOCALAPPDATA": str(local)}):
                paths = runpy.run_path(str(Path(__file__).resolve().parents[3] / "src" / "pointer" / "paths.py"))
            self.assertEqual(paths["INSTALL_ROOT"], installed.resolve())
            self.assertEqual(paths["DATA_ROOT"], installed.resolve().parent / "data")

    def make_package(self, root):
        (root / "Pointer.exe").write_bytes(b"test executable")
        (root / "VERSION").write_text("1.0.0", encoding="utf-8")
        data = {"version": "1.0.0", "files": {
            "Pointer.exe": hashlib.sha256((root / "Pointer.exe").read_bytes()).hexdigest()}}
        (root / "PACKAGE.json").write_text(json.dumps(data), encoding="utf-8")
        return data

    def test_rejects_damaged_package(self):
        with tempfile.TemporaryDirectory(prefix="Pointer 中文 ") as folder:
            root = Path(folder)
            self.make_package(root)
            self.assertEqual(len(installation.package_files(root)), 1)
            (root / "Pointer.exe").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "checksum"):
                installation.package_files(root)

    def test_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = self.make_package(root)
            data["files"]["../outside"] = "0" * 64
            (root / "PACKAGE.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid package path"):
                installation.package_files(root)

    def test_keeps_existing_original_backup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            old = root / "old"
            old.mkdir()
            current = root / "original.json"
            data = {"cursor_values": {"Arrow": {"value": "original", "type": 1}},
                    "previous_named_scheme": None}
            current.write_text(json.dumps(data), encoding="utf-8")
            with patch.object(config, "BACKUP", current):
                installation._migrate_backup(old)
            self.assertEqual(json.loads(current.read_text()), data)

    def test_invalid_backup_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            backup = Path(folder) / "backup.json"
            backup.write_text('{"unexpected":1}', encoding="utf-8")
            with patch.object(config, "BACKUP", backup):
                with self.assertRaises(ValueError):
                    installation._migrate_backup(Path(folder))
            self.assertEqual(backup.read_text(), '{"unexpected":1}')

    def test_start_failure_restores_startup_backup(self):
        from pointer.application import Application
        from pointer.cursor.settings import CursorSettings
        from pointer.windows import backend as boundary
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            data=Path(folder)/'data';data.mkdir()
            original=data/boundary.startup.STARTUP_BACKUP.name
            original.write_bytes(b'original startup backup')
            backend=boundary.WindowsBackend(data,Path(folder)/'app')
            stack.enter_context(patch.object(backend,'startup_enabled',return_value=True))
            stack.enter_context(patch.object(backend,'previous_installation',return_value=None))
            stack.enter_context(patch.object(backend,'stop'))
            stack.enter_context(patch.object(backend,'apply'))
            stack.enter_context(patch.object(boundary.engine,'running_directory',return_value=False))
            stack.enter_context(patch.object(boundary.scheme,'read_values',return_value={}))
            stack.enter_context(patch.object(boundary.scheme,'restore_values'))
            stack.enter_context(patch.object(boundary.scheme,'reload_cursors'))
            stack.enter_context(patch.object(boundary,'_run_value',return_value=None))
            def fail_start():
                original.write_bytes(b'changed')
                raise RuntimeError('not ready')
            stack.enter_context(patch.object(backend,'start',side_effect=fail_start))
            application=Application(data,Path(folder)/'app',backend)
            application.store.save(CursorSettings(startup=True))
            stack.enter_context(patch.object(app,'_application',return_value=application))
            with self.assertRaisesRegex(RuntimeError,'not ready'):
                app.apply_theme()
            self.assertEqual(original.read_bytes(),b'original startup backup')


class InstallerVersionTests(unittest.TestCase):
    def test_build_passes_numeric_and_display_versions_to_inno(self):
        from scripts import build_release
        from pointer.windows import composition_host

        for version, numeric in (('1.3.0-beta.6', '1.3.0.0'), ('2.4.5', '2.4.5.0')):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
                root = Path(folder)
                for directory in ('assets/cursors/adaptive', 'assets/cursors/reference',
                                  'web/cursor-test', 'packaging/windows/licenses'):
                    (root / directory).mkdir(parents=True)
                for name, content in {'VERSION': version, 'packaging/windows/README.txt': 'readme',
                                      'packaging/windows/pointer.ico': 'icon', 'runtime/LICENSE.txt': 'license',
                                      'helper.exe': 'helper', 'dist/Pointer/Pointer.exe': 'payload',
                                      'ISCC.exe': 'compiler'}.items():
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding='utf-8')
                compiler = root / 'ISCC.exe'
                installer = root / 'dist' / f'Pointer-v{version}-setup-x64.exe'
                stack.enter_context(patch.object(build_release, 'ROOT', root))
                stack.enter_context(patch.object(sys, 'base_prefix', str(root / 'runtime')))
                stack.enter_context(patch.object(build_release, 'verify_executable_icon'))
                stack.enter_context(patch.object(composition_host, 'prepare_helper', return_value=root / 'helper.exe'))
                distribution = stack.enter_context(patch.object(build_release.importlib.metadata, 'distribution'))
                distribution.return_value.files = []

                def compile_or_freeze(command, **kwargs):
                    if command[0] == str(compiler):
                        self.assertEqual(command, [str(compiler), f'/DAppVersion={version}',
                                                   f'/DAppNumericVersion={numeric}',
                                                   str(root / 'packaging/windows/installer.iss')])
                        self.assertTrue(kwargs['check'])
                        installer.write_bytes(b'compiled installer')

                run = stack.enter_context(patch.object(subprocess, 'run', side_effect=compile_or_freeze))
                result = build_release.build_release(version, compiler=compiler)
                self.assertEqual(run.call_count, 2)
                self.assertEqual(result['installer'], str(installer))
                self.assertEqual(result['installer_sha256'], hashlib.sha256(installer.read_bytes()).hexdigest())

    def test_installer_keeps_preview_text_separate_from_numeric_resources(self):
        root = Path(__file__).resolve().parents[3]
        template = (root / 'packaging/windows/installer.iss').read_text(encoding='utf-8')
        setup = template.split('[Setup]', 1)[1].split('[Languages]', 1)[0]
        values = dict(line.split('=', 1) for line in setup.splitlines() if '=' in line)
        for name in ('VersionInfoVersion', 'VersionInfoProductVersion'):
            self.assertEqual(values[name], '{#AppNumericVersion}')
        for name in ('AppVersion', 'VersionInfoTextVersion', 'VersionInfoProductTextVersion'):
            self.assertEqual(values[name], '{#AppVersion}')


if __name__ == "__main__":
    unittest.main()
