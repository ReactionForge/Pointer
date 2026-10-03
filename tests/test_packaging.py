"""Exercise backup preservation and damaged-package rejection without changing Windows."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import runpy
from contextlib import ExitStack
from unittest.mock import patch

import configure_cursor as config
import pointer_app as app


class PackageTests(unittest.TestCase):
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
                paths = runpy.run_path(str(Path(__file__).resolve().parents[1] / "runtime_paths.py"))
            self.assertEqual(paths["INSTALL_ROOT"], installed)
            self.assertEqual(paths["DATA_ROOT"], installed.parent / "data")

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
            stack.enter_context(patch.object(app.switcher, "stop"))
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
