"""Verify persisted mode choices and rotation without changing Windows settings."""

import json
import struct
import tempfile
import unittest
import subprocess
from pathlib import Path

from pointer import click_motion
from pointer import app
from unittest.mock import patch


class ClickModeTests(unittest.TestCase):
    def api(self):
        self.assertTrue(hasattr(click_motion, "read_mode"), "Persistent click modes are missing")
        return click_motion.read_mode, click_motion.save_mode

    def test_new_install_defaults_to_tilt(self):
        read, _ = self.api()
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(read(Path(folder) / "settings.json"), "tilt")

    def test_choice_survives_reload_and_invalid_choice_preserves_it(self):
        read, save = self.api()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "nested" / "settings.json"
            save(path, "shrink")
            self.assertEqual(read(path), "shrink")
            before = path.read_bytes()
            with self.assertRaises(ValueError):
                save(path, "unknown")
            self.assertEqual(path.read_bytes(), before)
            save(path, "tilt")
            self.assertEqual(read(path), "tilt")

    def test_corrupt_preference_falls_back_to_tilt(self):
        read, _ = self.api()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings.json"
            for data in ('broken', '[]', '{"mode":"unknown"}'):
                path.write_text(data)
                self.assertEqual(read(path), "tilt")


class TiltResourceTests(unittest.TestCase):
    def test_tilt_preserves_hotspots_area_and_rotates_clockwise(self):
        root = Path(__file__).resolve().parents[1] / "assets" / "cursors" / "adaptive"
        for theme in ("light", "dark"):
            for role in ("arrow", "hand"):
                normal = (root / theme / f"adaptive-{role}.cur").read_bytes()
                for frame in range(1, 5):
                    path = root / "tilt" / theme / f"{role}-{frame}.cur"
                    self.assertTrue(path.exists(), "Tilt frames are missing")
                    tilted = path.read_bytes()
                    for index in range(struct.unpack_from("<H", normal, 4)[0]):
                        entry = 6 + index * 16
                        self.assertEqual(tilted[entry:entry + 8], normal[entry:entry + 8])
                        if frame != 4:
                            continue
                        size = normal[entry] or 256
                        def shape(data):
                            offset = struct.unpack_from("<I", data, entry + 12)[0] + 40
                            pixels = data[offset:offset + size * size * 4]
                            points = [(n % size, size - 1 - n // size)
                                      for n, alpha in enumerate(pixels[3::4]) if alpha >= 128]
                            return len(points), sum(x for x, _ in points) / len(points)
                        area, center_x = shape(normal)
                        tilted_area, tilted_x = shape(tilted)
                        self.assertGreater(tilted_area, area * .94, (theme, role, size, "clipped"))
                        self.assertLess(tilted_area, area * 1.06)
                        self.assertLess(tilted_x, center_x, "Clockwise tilt around the tip moves the body left")


class ModeRecoveryTests(unittest.TestCase):
    def test_downloaded_mode_button_upgrades_an_older_installed_helper(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            installed = root / "installed"
            installed.mkdir()
            (installed / "Pointer.exe").touch()
            capability = installed / "assets/cursors/adaptive/tilt/light/arrow-4.cur"
            def install():
                capability.parent.mkdir(parents=True)
                capability.touch()
            def launch(arguments, **kwargs):
                report = Path(arguments[-1])
                value = {"exit_code": 0, "click_mode": "tilt"} if capability.exists() else {
                    "exit_code": 2, "error": "Older executable does not recognize --tilt"}
                report.write_text(json.dumps(value))
                return subprocess.CompletedProcess(arguments, value["exit_code"])
            with patch.object(app, "FROZEN", True), patch.object(app, "ROOT", root / "download"), \
                 patch.object(app, "INSTALL_ROOT", installed), patch.object(app, "DATA_ROOT", root), \
                 patch.object(app, "install", side_effect=install), \
                 patch.object(app.subprocess, "run", side_effect=launch):
                self.assertEqual(app.dispatch("tilt")["click_mode"], "tilt")

    def test_failed_mode_switch_restores_previous_preference(self):
        self.assertTrue(hasattr(app, "set_click_mode"), "Mode switching is missing")
        with tempfile.TemporaryDirectory() as folder:
            settings = Path(folder) / "settings.json"
            click_motion.save_mode(settings, "shrink")
            original = settings.read_bytes()
            with patch.object(app.switcher, "CLICK_SETTINGS", settings), \
                 patch.object(app, "apply_theme", side_effect=RuntimeError("helper failed")):
                with self.assertRaisesRegex(RuntimeError, "helper failed"):
                    app.set_click_mode("tilt")
            self.assertEqual(settings.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
