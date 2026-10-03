"""Keep press/release timing deterministic without injecting real mouse events."""

import importlib.util
import unittest
import struct
from pathlib import Path


class ClickMotionTests(unittest.TestCase):
    def motion(self):
        self.assertIsNotNone(importlib.util.find_spec("pointer.cursor.motion"),
                             "Click motion is not implemented")
        from pointer.cursor.motion import ClickMotion
        return ClickMotion()

    def test_configurable_press_and_release_durations(self):
        from pointer.cursor.motion import ClickMotion
        self.assertIn("press_ms", __import__("inspect").signature(ClickMotion).parameters)
        motion = ClickMotion(press_ms=200, release_ms=400)
        motion.update(True, 0)
        self.assertLess(motion.update(True, .05), 4)
        self.assertEqual(motion.update(True, .201), 4)
        motion.update(False, 1)
        self.assertGreater(motion.update(False, 1.3), 0)
        self.assertEqual(motion.update(False, 1.401), 0)

    def test_press_holds_until_release_and_returns_to_rest(self):
        motion = self.motion()
        self.assertEqual(motion.update(False, 0), 0)
        motion.update(True, 1)
        self.assertEqual(motion.update(True, 1.061), 4)
        self.assertEqual(motion.update(True, 10), 4)
        self.assertEqual(motion.update(False, 10), 4)
        middle = motion.update(False, 10.04)
        self.assertGreater(middle, 0)
        self.assertLess(middle, 4)
        self.assertEqual(motion.update(False, 10.151), 0)
        self.assertEqual(motion.presses, 1)

    def test_quick_release_finishes_without_getting_stuck(self):
        motion = self.motion()
        motion.update(True, 0)
        motion.update(True, .015)
        motion.update(False, .016)
        self.assertEqual(motion.update(False, .167), 0)
        self.assertEqual(motion.presses, 1)

    def test_rebound_remains_visible_near_150_milliseconds(self):
        motion = self.motion()
        motion.update(True, 0)
        motion.update(True, .061)
        motion.update(False, 1)
        self.assertGreater(motion.update(False, 1.13), 0)
        self.assertEqual(motion.update(False, 1.151), 0)

    def test_new_press_during_rebound_reverses_without_a_jump(self):
        motion = self.motion()
        motion.update(True, 0)
        motion.update(True, .061)
        motion.update(False, .1)
        before = motion.update(False, .14)
        self.assertEqual(motion.update(True, .14), before)
        self.assertEqual(motion.update(True, .201), 4)
        motion.update(False, .3)
        self.assertEqual(motion.update(False, .451), 0)
        self.assertEqual(motion.presses, 2)


class ClickResourceTests(unittest.TestCase):
    def test_pressed_frames_keep_all_hotspots_and_shrink_the_silhouette(self):
        root = Path(__file__).resolve().parents[3] / "assets" / "cursors" / "adaptive"
        for theme in ("light", "dark"):
            for role in ("arrow", "hand"):
                normal = (root / theme / f"adaptive-{role}.cur").read_bytes()
                for frame in range(1, 5):
                    path = root / "click" / theme / f"{role}-{frame}.cur"
                    self.assertTrue(path.is_file(), f"Missing click cursor: {path}")
                    pressed = path.read_bytes()
                    self.assertEqual(pressed[:6], normal[:6])
                    count = struct.unpack_from("<H", normal, 4)[0]
                    for index in range(count):
                        entry = 6 + index * 16
                        self.assertEqual(pressed[entry:entry + 8], normal[entry:entry + 8])
                        if frame != 4:
                            continue
                        width = normal[entry] or 256
                        def area(data):
                            offset = struct.unpack_from("<I", data, entry + 12)[0] + 40
                            pixels = data[offset:offset + width * width * 4]
                            return sum(alpha >= 128 for alpha in pixels[3::4])
                        self.assertLess(area(pressed), area(normal) * .95)
                        self.assertGreater(area(pressed), area(normal) * .70)


if __name__ == "__main__":
    unittest.main()
