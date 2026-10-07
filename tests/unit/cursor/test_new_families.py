"""Real-size, role-wide invariants for the new families and legacy compatibility."""
import unittest
from dataclasses import replace
from pointer.cursor.resources import RenderRequest, render_cursor, encode_cur
from pointer.cursor.settings import CursorSettings
from pointer.cursor.theme import FILENAMES
ROLE_IDS = tuple(name.split('.')[0] for name in FILENAMES.values())
from pointer.cursor.art.catalog import RENDERERS
from pointer.cursor.art.families import STYLES


class NewFamilyTests(unittest.TestCase):
    def test_all_roles_sizes_backgrounds_have_geometry_and_stable_native_hotspots(self):
        for style in STYLES:
            for size in (24, 32, 48, 64):
                for role in ROLE_IDS:
                    settings = CursorSettings(style=style, size=size)
                    samples = [render_cursor(RenderRequest(settings, role, theme)) for theme in ('light', 'dark')]
                    self.assertEqual(samples[0][1], samples[1][1])
                    for image, hotspot in samples:
                        self.assertIsNotNone(image.getchannel('A').getbbox(), (style, size, role))
                        x0, y0, x1, y1 = image.getchannel('A').getbbox()
                        self.assertTrue(0 < x0 < x1 < image.width and 0 < y0 < y1 < image.height)
                        self.assertTrue(0 <= hotspot[0] < image.width and 0 <= hotspot[1] < image.height)
                        if role in ('arrow', 'hand', 'pen', 'up', 'pin', 'person'):
                            self.assertGreater(image.getpixel(hotspot)[3], 0, (style, size, role, 'unpainted hotspot'))
                    raw = encode_cur(samples[:1])
                    self.assertEqual(raw[:4], b'\x00\x00\x02\x00')

    def test_styles_change_whole_families_not_only_arrow(self):
        for role in ROLE_IDS:
            masks = [render_cursor(RenderRequest(CursorSettings(style=style), role))[0].tobytes()
                     for style in STYLES]
            self.assertEqual(len(set(masks)), len(STYLES), role)

    def test_new_click_frames_keep_hotspot_and_clear_bounds_at_extreme_strength(self):
        for style in STYLES:
            for size in (24, 32, 48, 64):
                for role in ('arrow', 'hand'):
                    settings = CursorSettings(style=style, size=size, motion='shrink', strength=100)
                    frames = [render_cursor(RenderRequest(settings, role, 'light', frame)) for frame in range(5)]
                    self.assertEqual(len({hotspot for _, hotspot in frames}), 1)
                    for image, _ in frames:
                        x0, y0, x1, y1 = image.getchannel('A').getbbox()
                        self.assertTrue(0 < x0 < x1 < image.width and 0 < y0 < y1 < image.height)

    def test_legacy_styles_and_custom_palette_round_trip_without_migration(self):
        for style in ('sequoia', 'outline', 'precision', 'falcon', 'pixel'):
            original = CursorSettings(style=style, light_body='#112233', dark_outline='#aabbcc')
            self.assertEqual(CursorSettings.from_dict(original.to_dict()), original)
