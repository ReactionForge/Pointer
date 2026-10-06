"""Loading rings stay solid when magnified or rendered for high DPI."""
import math
import unittest

from pointer.cursor.art.animation import render_loading


class LoadingArtTests(unittest.TestCase):
    def test_arc_body_has_no_radial_seams_in_any_frame(self):
        for size in (96, 160):
            for with_arrow, center, radius in (
                (False, (16, 16), 10), (True, (25, 24), 4.5)
            ):
                for frame in range(24):
                    image = render_loading(size, frame, with_arrow)
                    # Probe the interior, away from the antialiased contour and caps.
                    for offset in range(20, 251, 2):
                        angle = math.radians(frame * 15 + offset)
                        point = tuple(round(value * size / 32) for value in (
                            center[0] + radius * math.cos(angle),
                            center[1] + radius * math.sin(angle),
                        ))
                        rgba = image.getpixel(point)
                        with self.subTest(size=size, working=with_arrow, frame=frame, point=point):
                            self.assertGreaterEqual(rgba[3], 250, "Transparent seam inside ring")
                            self.assertLessEqual(max(rgba[:3]), 24, "Outline leaks into ring body")

    def test_rotating_ring_keeps_an_open_gap_and_round_caps(self):
        for frame in range(24):
            image = render_loading(160, frame)
            for offset in (0, 270):
                angle = math.radians(frame * 15 + offset)
                point = (round(80 + 50 * math.cos(angle)), round(80 + 50 * math.sin(angle)))
                self.assertEqual(image.getpixel(point)[3], 255)
            gap = math.radians(frame * 15 + 315)
            point = (round(80 + 50 * math.cos(gap)), round(80 + 50 * math.sin(gap)))
            self.assertEqual(image.getpixel(point)[3], 0)
            self.assertEqual(image.getpixel((80, 80))[3], 0)
