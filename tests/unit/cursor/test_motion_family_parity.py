"""Style changes must preserve the press transform and native resource path."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from pointer.cursor.art.families import RECOMMENDED_STYLES
from pointer.cursor.resources import RenderRequest, render_cursor, prepare_resources
from pointer.cursor.settings import CursorSettings


class MotionFamilyParityTests(unittest.TestCase):
    def test_same_press_transform_and_hotspot_across_all_recommended_families(self):
        original = Image.Image.transform
        for role in ('arrow', 'hand'):
            for mode in ('tilt', 'shrink', 'spring'):
                for frame in range(1, 5):
                    matrices, hotspots = [], []
                    for style in RECOMMENDED_STYLES:
                        def capture(image, size, method, data, *args, **kwargs):
                            matrices.append(data)
                            return original(image, size, method, data, *args, **kwargs)
                        with patch.object(Image.Image, 'transform', capture):
                            _, hotspot = render_cursor(RenderRequest(CursorSettings(style=style, motion=mode), role, frame=frame))
                            hotspots.append(hotspot)
                    self.assertEqual(len(set(matrices)), 1, (role, mode, frame))
                    self.assertEqual(len(set(hotspots)), 1)

    def test_default_animated_family_preserves_approved_original_press_assets(self):
        with tempfile.TemporaryDirectory() as folder:
            bundle = prepare_resources(CursorSettings(), Path(folder))
            self.assertTrue(bundle.builtin)
            self.assertTrue(bundle.paths('light', 4)['Arrow'].is_file())
            self.assertNotEqual(bundle.paths('light', 0)['Arrow'].read_bytes(),
                                bundle.paths('light', 4)['Arrow'].read_bytes())
