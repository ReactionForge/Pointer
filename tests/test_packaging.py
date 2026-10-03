"""Exercise backup preservation and damaged-package rejection without changing Windows."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import runpy
import subprocess
import sys
from contextlib import ExitStack
from unittest.mock import patch

from pointer import configure_cursor as config
from pointer import app


class PackageTests(unittest.TestCase):
    def test_reapplying_preserves_startup_registration(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            stack.enter_context(patch.object(config, "BACKUP", Path(folder) / "absent.json"))
            stack.enter_context(patch.object(app.switcher, "STARTUP_BACKUP", Path(folder) / "absent-startup.json"))
            stack.enter_context(patch.object(app, "_snapshot", return_value={}))
            stack.enter_context(patch.object(app, "_run_value", return_value=None))
            stop = stack.enter_context(patch.object(app.switcher, "stop"))
            stop_directory = stack.enter_context(patch.object(app.switcher, "stop_directory"))
            stack.enter_context(patch.object(config, "apply"))
            stack.enter_context(patch.object(app.switcher, "enable_startup"))
            stack.enter_context(patch.object(app.switcher, "start", return_value={"running": True, "pid": 123}))
            self.assertTrue(app.apply_theme()["startup_enabled"])
            stop.assert_not_called()
            stop_directory.assert_called_once_with(app.ROOT)

    def test_identical_startup_entry_is_never_rewritten(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            startup = Path(folder) / "startup.json"
            startup.write_bytes(b'{"previous": null, "installed_command": "unchanged"}')
            original = startup.read_bytes()
            stack.enter_context(patch.object(app.switcher, "STARTUP_BACKUP", startup))
            stack.enter_context(patch.object(app.switcher, "_startup_command", return_value="unchanged"))
            stack.enter_context(patch.object(app.winreg, "CreateKeyEx"))
            stack.enter_context(patch.object(app.winreg, "QueryValueEx", return_value=("unchanged", app.winreg.REG_SZ)))
            write = stack.enter_context(patch.object(app.winreg, "SetValueEx"))
            backup = stack.enter_context(patch.object(app.switcher, "_atomic_json"))
            for _ in range(5):
                self.assertFalse(app.switcher.enable_startup()["changed"])
            write.assert_not_called()
            backup.assert_not_called()
            self.assertEqual(startup.read_bytes(), original)

    def test_startup_upgrade_keeps_original_backup(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            startup = Path(folder) / "startup.json"
            startup.write_text(json.dumps({"value_name": app.switcher.RUN_VALUE,
                                          "previous": None, "installed_command": "old path"}))
            stack.enter_context(patch.object(app.switcher, "STARTUP_BACKUP", startup))
            stack.enter_context(patch.object(app.switcher, "_startup_command", return_value="new path"))
            stack.enter_context(patch.object(app.winreg, "CreateKeyEx"))
            stack.enter_context(patch.object(app.winreg, "QueryValueEx", return_value=("old path", app.winreg.REG_SZ)))
            write = stack.enter_context(patch.object(app.winreg, "SetValueEx"))
            self.assertTrue(app.switcher.enable_startup()["changed"])
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
            app.remove_obsolete_files(previous, {}, root)
            self.assertFalse(old.parent.exists())
            self.assertEqual(changed.read_bytes(), b"user change")
            self.assertEqual(unowned.read_text(), "user notes")

    def test_source_entrypoint_works_without_site_packages_from_another_directory(self):
        repository = Path(__file__).resolve().parents[1]
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
                 patch.dict(app.os.environ, {"LOCALAPPDATA": str(local)}):
                paths = runpy.run_path(str(Path(__file__).resolve().parents[1] / "src" / "pointer" / "runtime_paths.py"))
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
            self.assertEqual(len(app.package_files(root)), 1)
            (root / "Pointer.exe").write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "checksum"):
                app.package_files(root)

    def test_rejects_path_escape(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = self.make_package(root)
            data["files"]["../outside"] = "0" * 64
            (root / "PACKAGE.json").write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid package path"):
                app.package_files(root)

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
                app._migrate_backup(old)
            self.assertEqual(json.loads(current.read_text()), data)

    def test_invalid_backup_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            backup = Path(folder) / "backup.json"
            backup.write_text('{"unexpected":1}', encoding="utf-8")
            with patch.object(config, "BACKUP", backup):
                with self.assertRaises(ValueError):
                    app._migrate_backup(Path(folder))
            self.assertEqual(backup.read_text(), '{"unexpected":1}')

    def test_start_failure_restores_startup_backup(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            startup = Path(folder) / "startup.json"
            startup.write_bytes(b"original startup backup")
            stack.enter_context(patch.object(app.switcher, "STARTUP_BACKUP", startup))
            stack.enter_context(patch.object(config, "BACKUP", Path(folder) / "absent.json"))
            before = {"cursor_values": {}, "previous_named_scheme": None}
            stack.enter_context(patch.object(app, "_snapshot", return_value=before))
            stack.enter_context(patch.object(app, "_run_value", return_value=None))
            stack.enter_context(patch.object(app.switcher, "stop_directory"))
            stack.enter_context(patch.object(config, "apply"))
            stack.enter_context(patch.object(app.switcher, "enable_startup", side_effect=lambda: startup.write_bytes(b"changed")))
            stack.enter_context(patch.object(app.switcher, "start", side_effect=RuntimeError("not ready")))
            restored = stack.enter_context(patch.object(config, "restore_values"))
            stack.enter_context(patch.object(config, "reload_cursors"))
            stack.enter_context(patch.object(app.winreg, "CreateKeyEx"))
            stack.enter_context(patch.object(config, "restore_value"))
            with self.assertRaisesRegex(RuntimeError, "not ready"):
                app.apply_theme()
            restored.assert_called_once_with(before)
            self.assertEqual(startup.read_bytes(), b"original startup backup")


if __name__ == "__main__":
    unittest.main()
