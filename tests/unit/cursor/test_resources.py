"""Geometry, DPI and cache integrity for configurable native cursor files."""
from dataclasses import replace
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pointer.cursor.settings import CursorSettings


class ResourceTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('pointer.cursor.resources'), 'Resource API missing')
        from pointer.cursor import resources
        self.api = resources

    def test_extreme_settings_safe_bounds_and_stable_hotspots(self):
        for size in (24, 32, 40, 48, 64):
            for dpi in (96, 144, 192, 288, 384, 768):
                for role in ('arrow', 'hand'):
                    settings = CursorSettings(size=size, strength=100)
                    frames = [self.api.render_cursor(self.api.RenderRequest(settings, role, 'dark', f, dpi)) for f in range(5)]
                    self.assertEqual(len({hotspot for _, hotspot in frames}), 1)
                    for image, _ in frames:
                        box = image.getchannel('A').getbbox()
                        self.assertIsNotNone(box)
                        x0, y0, x1, y1 = box
                        self.assertGreater(x0, 0, (size, dpi, role))
                        self.assertGreater(y0, 0, (size, dpi, role))
                        self.assertLess(x1, image.width, (size, dpi, role))
                        self.assertLess(y1, image.height, (size, dpi, role))

    def test_off_and_zero_strength_do_not_move(self):
        for settings in (CursorSettings(motion='off'), CursorSettings(strength=0)):
            for role in ('arrow', 'hand'):
                normal, hot = self.api.render_cursor(self.api.RenderRequest(settings, role, 'light', 0, 96))
                pressed, pressed_hot = self.api.render_cursor(self.api.RenderRequest(settings, role, 'light', 4, 96))
                self.assertEqual(normal.tobytes(), pressed.tobytes())
                self.assertEqual(hot, pressed_hot)

    def test_palette_colors_and_size_change_visible_cursor(self):
        settings = CursorSettings(light_body='#c83228', light_outline='#1464a0')
        image, _ = self.api.render_cursor(self.api.RenderRequest(settings, 'arrow', 'light', 0, 96))
        colors = {pixel[:3] for pixel in image.get_flattened_data() if pixel[3] == 255}
        self.assertIn((200, 50, 40), colors)
        self.assertIn((20, 100, 160), colors)
        large, _ = self.api.render_cursor(self.api.RenderRequest(replace(settings, size=64), 'arrow', 'light', 0, 96))
        box, large_box = image.getchannel('A').getbbox(), large.getchannel('A').getbbox()
        self.assertGreater(large_box[2] - large_box[0], (box[2] - box[0]) * 1.8)

    def test_generated_cache_reused_and_failure_preserves_it(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = CursorSettings(light_body='#224466', size=24)
            bundle = self.api.prepare_resources(settings, Path(folder))
            before = {p: p.read_bytes() for p in bundle.root.rglob('*') if p.is_file()}
            with patch.object(self.api, '_generate_bundle', side_effect=RuntimeError('generation failed')):
                reused = self.api.prepare_resources(settings, Path(folder))
                self.assertEqual(reused.root, bundle.root)
                with self.assertRaisesRegex(RuntimeError, 'generation failed'):
                    self.api.prepare_resources(replace(settings, strength=60), Path(folder))
            self.assertTrue(all(p.read_bytes() == value for p, value in before.items()))
            self.assertTrue(bundle.paths('dark')['Wait'].read_bytes().startswith(b'RIFF'))

    def test_tampered_cache_is_rebuilt_without_deleting_other_files(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = CursorSettings(size=24, dark_body='#eeeeee')
            bundle = self.api.prepare_resources(settings, Path(folder))
            cursor = bundle.paths('light')['Arrow']
            cursor.write_bytes(b'damaged')
            note = bundle.root / 'user-note.txt'
            note.write_text('keep')
            repaired = self.api.prepare_resources(settings, Path(folder))
            self.assertNotEqual(repaired.root, bundle.root)
            self.assertEqual(note.read_text(), 'keep')
            self.assertNotEqual(repaired.paths('light')['Arrow'].read_bytes(), b'damaged')

    def test_ani_loads_at_requested_sizes_with_real_animation(self):
        from pointer.cursor.art.animation import render_loading
        from pointer.windows import engine
        variants = (32, 48, 64, 96, 128, 256)
        frames = [self.api.encode_cur([(render_loading(size, f), (size//2, size//2))
                                      for size in variants]) for f in range(24)]
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "custom.ani"
            path.write_bytes(self.api.encode_ani(frames))
            for size in (32, 44, 66, 128):
                cursor = engine.USER32.LoadImageW(None, str(path), 2, size, size, 0x10)
                self.assertTrue(cursor, "Native Windows loader rejected generated ANI")
                try:
                    self.assertTrue(engine._has_animation(cursor))
                finally:
                    engine.USER32.DestroyCursor(cursor)

    def test_malformed_cache_manifest_is_not_trusted(self):
        import json
        settings = CursorSettings(size=24)
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            key = self.api._render_key(settings)
            damaged = root / "damaged"
            damaged.mkdir()
            (damaged / "MANIFEST.json").write_text(json.dumps({"key":key,"files":["bad"]}))
            (root / (key + ".json")).write_text('{"folder":"damaged"}')
            with patch.object(self.api, "_generate_bundle", side_effect=RuntimeError("regenerate")):
                with self.assertRaisesRegex(RuntimeError, "regenerate"):
                    self.api.prepare_resources(settings, root)
            self.assertTrue((damaged / "MANIFEST.json").exists())

    def test_concurrent_prepare_resources_returns_valid_shared_bundle(self):
        import concurrent.futures
        settings = CursorSettings(size=24, dark_body="#123456")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
                futures = [ex.submit(self.api.prepare_resources, settings, root) for _ in range(4)]
                bundles = [f.result() for f in futures]
            self.assertEqual(len({b.root for b in bundles}), 1)
            self.assertEqual(len({b.key for b in bundles}), 1)
            self.assertTrue(bundles[0].paths('light')['Arrow'].exists())

    def test_concurrent_prepare_resources_different_keys_use_independent_locks(self):
        import concurrent.futures
        s1 = CursorSettings(size=24, dark_body="#111111")
        s2 = CursorSettings(size=24, dark_body="#222222")
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
                f1 = ex.submit(self.api.prepare_resources, s1, root)
                f2 = ex.submit(self.api.prepare_resources, s2, root)
                b1, b2 = f1.result(), f2.result()
            self.assertNotEqual(b1.key, b2.key)
            self.assertTrue(b1.paths('light')['Arrow'].exists())
            self.assertTrue(b2.paths('light')['Arrow'].exists())
