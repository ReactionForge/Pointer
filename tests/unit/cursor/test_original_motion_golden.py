"""Immutable pre-V3 rounded oracles, sourced from Git 3511e3, never current output."""
import hashlib
import json
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pointer.cursor.motion import ClickMotion
from pointer.cursor.resources import RenderRequest, render_cursor, prepare_resources
from pointer.cursor.settings import CursorSettings
from pointer.cursor.art.families import RECOMMENDED_STYLES

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = json.loads((ROOT/'tests/fixtures/original-rounded-motion.json').read_text())
sha = lambda content: hashlib.sha256(content).hexdigest()


class OriginalMotionGoldenTests(unittest.TestCase):
    def test_original_native_assets_and_default_resource_selection_are_unchanged(self):
        for path, digest in GOLDEN['asset_sha256'].items():
            self.assertEqual(sha((ROOT/path).read_bytes()), digest, path)
        with tempfile.TemporaryDirectory() as folder:
            for mode in ('tilt', 'shrink'):
                bundle = prepare_resources(CursorSettings(motion=mode), Path(folder))
                self.assertTrue(bundle.builtin)
                for theme in ('light', 'dark'):
                    for frame in range(5):
                        for path in bundle.paths(theme, frame).values():
                            relative = path.relative_to(ROOT).as_posix()
                            if relative in GOLDEN['asset_sha256']:
                                self.assertEqual(sha(path.read_bytes()), GOLDEN['asset_sha256'][relative])

    def test_rounded_preview_matches_original_pixels_and_hotspots_not_v3(self):
        for key, reference in GOLDEN['historical_preview'].items():
            mode, theme, role, size, dpi, frame = key.split('/')
            image, hotspot = render_cursor(RenderRequest(CursorSettings(motion=mode, size=int(size)), role,
                                                         theme, int(frame), int(dpi)))
            self.assertEqual(sha(image.tobytes()), reference['rgba_sha256'], key)
            self.assertEqual(list(hotspot), reference['hotspot'], key)

    def test_click_clock_matches_original_all_stored_modes_and_releases(self):
        for mode, expected in GOLDEN['timelines'].items():
            motion = ClickMotion(mode=mode)
            self.assertEqual([motion.update(down, now) for down, now in GOLDEN['time_inputs']], expected)
        self.assertEqual(sha((ROOT/'src/pointer/cursor/motion.py').read_bytes().replace(b'\r\n', b'\n')),
                         GOLDEN['clock_source_sha256'])

    def test_retired_overlay_modes_never_add_pixels_and_preserve_stored_settings(self):
        for style in RECOMMENDED_STYLES:
            for mode in ('trail', 'pulse'):
                settings = CursorSettings(style=style, motion=mode)
                self.assertEqual(CursorSettings.from_dict(settings.to_dict()), settings)
                for role in ('arrow', 'hand'):
                    neutral, hotspot = render_cursor(RenderRequest(settings, role))
                    for frame in range(1, 5):
                        image, point = render_cursor(RenderRequest(settings, role, frame=frame))
                        self.assertEqual(image.tobytes(), neutral.tobytes())
                        self.assertEqual(point, hotspot)

    def test_generated_native_frames_match_each_family_preview_without_duplicate_subjects(self):
        from pointer.cursor import resources
        for style in RECOMMENDED_STYLES[1:]:
            settings = CursorSettings(style=style)
            with tempfile.TemporaryDirectory() as folder, patch.object(resources, 'DPI_VARIANTS', (96, 192)), \
                    patch.dict(resources.FILENAMES, {'Arrow': 'arrow.cur', 'Hand': 'hand.cur'}, clear=True):
                bundle = prepare_resources(settings, Path(folder))
                for frame in range(5):
                    for role, native in (('arrow', 'Arrow'), ('hand', 'Hand')):
                        raw = bundle.paths('light', frame)[native].read_bytes()
                        for index in range(struct.unpack_from('<H', raw, 4)[0]):
                            width, height, _, _, hx, hy, _, offset = struct.unpack_from('<BBBBHHII', raw, 6+16*index)
                            width, height = width or 256, height or 256
                            dpi = 96 if width == 62 else 192
                            image, hotspot = render_cursor(RenderRequest(settings, role, 'light', frame, dpi))
                            # Native DIB uses bottom-up rows; compare exact raster
                            # independently of the CUR writer, including alpha.
                            from PIL import Image
                            decoded = Image.frombytes('RGBA', (width, height), raw[offset+40:offset+40+width*height*4],
                                                      'raw', 'BGRA', 0, -1)
                            self.assertEqual(decoded.tobytes(), image.tobytes(), (style, role, frame, dpi))
                            self.assertEqual((hx, hy), hotspot)
                            mask = decoded.getchannel('A')
                            remaining = {(x, y) for y in range(height) for x in range(width) if mask.getpixel((x, y)) >= 128}
                            components = 0
                            while remaining:
                                components += 1
                                pending = [remaining.pop()]
                                while pending:
                                    x, y = pending.pop()
                                    for dx in (-1, 0, 1):
                                        for dy in (-1, 0, 1):
                                            point = x+dx, y+dy
                                            if point in remaining:
                                                remaining.remove(point)
                                                pending.append(point)
                            self.assertEqual(components, 1, (style, role, frame, 'multiple solid silhouettes'))
