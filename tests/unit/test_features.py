"""Comprehensive unit tests for styles, palettes, aura glow, spring motion, and theme packages."""
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image

from pointer.cursor.settings import CursorSettings, SettingsStore, STYLES, MOTIONS
from pointer.cursor.art.arrow import arrow_contour, render as render_arrow
from pointer.cursor.resources import RenderRequest, render_cursor
from pointer.cursor.motion import ClickMotion
from pointer.ui.pages.appearance import PRESETS, CORE_PRESETS, TRENDY_PRESETS
from pointer.windows.engine import _is_fullscreen_game


class FeatureTests(unittest.TestCase):
    def test_four_geometric_styles(self):
        self.assertEqual(len(STYLES), 4)
        for style in ('sequoia', 'precision', 'falcon', 'pixel'):
            contour = arrow_contour(style=style)
            self.assertGreater(len(contour), 3)
            # Origin tip should remain anchored at (3, 3) or near top left
            self.assertAlmostEqual(contour[0][0], 3.0, delta=3.5)
            self.assertAlmostEqual(contour[0][1], 3.0, delta=3.5)
            
            # Test rendering at various sizes
            for size in (24, 32, 48):
                img = render_arrow(size, style=style)
                self.assertEqual(img.size, (size, size))
                bbox = img.getchannel('A').getbbox()
                self.assertIsNotNone(bbox)
                self.assertGreater(bbox[2] - bbox[0], size * 0.3)

    def test_eight_curated_palettes(self):
        self.assertEqual(len(PRESETS), 8)
        self.assertEqual(len(CORE_PRESETS), 4)
        self.assertEqual(len(TRENDY_PRESETS), 4)
        expected_ids = {'classic', 'aurora', 'obsidian', 'geek', 'cyber', 'mist', 'sakura', 'abyssal'}
        actual_ids = {p['id'] for p in PRESETS}
        self.assertEqual(actual_ids, expected_ids)

        for preset in PRESETS:
            for key in ('light_body', 'light_outline', 'dark_body', 'dark_outline'):
                color = preset[key]
                self.assertTrue(color.startswith('#'))
                self.assertEqual(len(color), 7)

    def test_aura_glow_generation(self):
        s_normal = CursorSettings(aura_glow=False)
        s_glow = CursorSettings(aura_glow=True, aura_color='#ff007f')
        
        img_normal, hot_normal = render_cursor(RenderRequest(s_normal, 'arrow', 'light', 0, 96))
        img_glow, hot_glow = render_cursor(RenderRequest(s_glow, 'arrow', 'light', 0, 96))
        
        self.assertEqual(hot_normal, hot_glow)
        # Glow layer adds translucent pixels in the outer margin
        alpha_normal = img_normal.getchannel('A')
        alpha_glow = img_glow.getchannel('A')
        
        box_normal = alpha_normal.getbbox()
        box_glow = alpha_glow.getbbox()
        
        # Glow bounding box should be strictly wider/larger or equal than normal
        self.assertLessEqual(box_glow[0], box_normal[0])
        self.assertGreaterEqual(box_glow[2], box_normal[2])

    def test_motion_dynamics_modes(self):
        for mode in ('tilt', 'shrink', 'spring', 'pulse', 'trail'):
            settings = CursorSettings(motion=mode, strength=60)
            motion = ClickMotion(press_ms=60, release_ms=150, mode=mode)
            
            # Verify frame transitions
            frame_down = motion.update(True, 0.05)
            self.assertGreaterEqual(frame_down, 0)
            self.assertLessEqual(frame_down, 4)
            
            frame_up = motion.update(False, 0.20)
            self.assertGreaterEqual(frame_up, 0)
            self.assertLessEqual(frame_up, 4)

            # Verify render_cursor produces non-empty frames without error
            for f in range(5):
                img, hot = render_cursor(RenderRequest(settings, 'arrow', 'light', f, 96))
                self.assertIsNotNone(img.getchannel('A').getbbox())

    def test_pointertheme_package_roundtrip(self):
        with tempfile.TemporaryDirectory() as folder:
            theme_path = Path(folder) / "NeonFalcon.pointertheme"
            store = SettingsStore(folder)
            
            orig_settings = CursorSettings(
                style='falcon',
                motion='spring',
                aura_glow=True,
                aura_color='#ff007f',
                light_body='#12092b',
                light_outline='#ff007f',
                dark_body='#00f0ff',
                dark_outline='#7928ca',
            )
            
            store.export_theme(
                theme_path,
                orig_settings,
                name="Cyber Falcon Glow",
                author="Designer",
                desc="High performance mecha theme"
            )
            
            self.assertTrue(theme_path.exists())
            raw_content = json.loads(theme_path.read_text(encoding='utf-8'))
            self.assertEqual(raw_content['format'], 'pointertheme')
            self.assertEqual(raw_content['metadata']['name'], 'Cyber Falcon Glow')
            
            # Import via import_theme
            loaded_settings, meta = store.import_theme(theme_path)
            self.assertEqual(loaded_settings, orig_settings)
            self.assertEqual(meta['author'], 'Designer')
            
            # Import via import_file (auto-detects pointertheme format)
            file_settings = store.import_file(theme_path)
            self.assertEqual(file_settings, orig_settings)


if __name__ == '__main__':
    unittest.main()
