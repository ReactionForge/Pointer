"""Fast publication regression checks; no desktop or FFmpeg dependency."""
import json
import tempfile
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
import wave
from PIL import Image

from scripts.render_promo import DURATION, SCENES, scene_at, subtitle_text, sprite, synth_audio, main


class PromoTests(unittest.TestCase):
    def test_scenes_cover_exact_fifty_seconds(self):
        self.assertEqual(SCENES[0][0], 0)
        self.assertEqual(SCENES[-1][1], DURATION)
        for previous, following in zip(SCENES, SCENES[1:]):
            self.assertEqual(previous[1], following[0])
        for index, (start, end, *_rest) in enumerate(SCENES):
            self.assertEqual(scene_at(start), index)
            self.assertEqual(scene_at(end - .01), index)

    def test_subtitles_include_both_languages_and_end_at_fifty(self):
        value = subtitle_text()
        self.assertIn('00:00:42,000 --> 00:00:50,000', value)
        self.assertEqual(value.count(' --> '), len(SCENES))
        for _start, _end, chinese, english in SCENES:
            self.assertIn(chinese, value)
            self.assertIn(english, value)

    def test_motion_preserves_sprite_bounds_and_changes_pixels(self):
        neutral = sprite(frame=0, extent=120)
        pressed = sprite(frame=4, extent=120)
        self.assertEqual(neutral.size, pressed.size)
        self.assertLessEqual(max(neutral.size), 120)
        self.assertNotEqual(neutral.tobytes(), pressed.tobytes())
        self.assertEqual(neutral.mode, 'RGBA')

    def test_capture_has_no_system_or_prewarm_actions(self):
        # Keep the renderer's native Qt object lifetime separate from the
        # parent suite's long-lived QApplication and Shiboken wrappers.
        with tempfile.TemporaryDirectory() as root:
            subprocess.run([sys.executable, '-c',
                            'import sys; from pathlib import Path; from scripts.render_promo import capture_ui; '
                            'images=capture_ui(Path(sys.argv[1])); '
                            'assert set(images)=={"appearance","motion","tests","settings"}', root],
                           check=True, timeout=45, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            with Image.open(Path(root)/'app-appearance.png') as image:
                self.assertEqual(image.size, (1180, 800))
            # Child capture asserts actual prewarm entrypoints and writes blocked.

    def _mocked_render(self, root, flags):
        output = root/'output'
        output.mkdir()
        (output/'manifest.json').write_text('previous provenance', encoding='utf8')
        (output/'unrelated.mp4').write_bytes(b'unrelated')
        font = root/'local-font.ttf'
        font.write_bytes(b'font fingerprint fixture')
        film = Mock()
        film.width, film.height = 1080, 1920
        film.frame.return_value = Image.new('RGB', (16, 16), '#223344')
        args = ['render-promo', '--output', str(output), '--media', str(root/'media'), '--ffmpeg', 'fixture', *flags]
        with patch('sys.argv', args), patch('scripts.render_promo.capture_ui', return_value={}), \
             patch('scripts.render_promo.font_path', return_value=str(font)), \
             patch('scripts.render_promo.Film', return_value=film), \
             patch('scripts.render_promo.synth_audio'), \
             patch('scripts.render_promo.subprocess.check_output', return_value='ffmpeg fixture\n'), \
             patch('scripts.render_promo.encode', side_effect=lambda _film, path, *_args: path.write_bytes(b'new video')):
            main()
        self.assertEqual((output/'manifest.json').read_text(encoding='utf8'), 'previous provenance')
        self.assertEqual((output/'unrelated.mp4').read_bytes(), b'unrelated')
        return output

    def test_still_run_does_not_relabel_old_videos(self):
        with tempfile.TemporaryDirectory() as folder:
            output = self._mocked_render(Path(folder), ['--stills-only'])
            manifest = json.loads((output/'stills-manifest.json').read_text(encoding='utf8'))
            self.assertEqual(manifest['video_files'], {})
            self.assertEqual(manifest['formats'], {})

    def test_single_format_manifest_only_lists_new_video(self):
        with tempfile.TemporaryDirectory() as folder:
            output = self._mocked_render(Path(folder), ['--format', 'portrait'])
            manifest = json.loads((output/'manifest-portrait.json').read_text(encoding='utf8'))
            self.assertEqual(set(manifest['formats']), {'portrait'})
            self.assertEqual(list(manifest['video_files']), ['Pointer-v1.3.0-beta.6-demo-portrait.mp4'])

    def test_procedural_audio_format(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root)/'audio.wav'
            synth_audio(target, duration=1)
            with wave.open(str(target), 'rb') as source:
                self.assertEqual(source.getframerate(), 24000)
                self.assertEqual(source.getnchannels(), 1)
                self.assertEqual(source.getsampwidth(), 2)
                self.assertEqual(source.getnframes(), 24000)
                self.assertNotEqual(source.readframes(24000), bytes(48000))


if __name__ == '__main__':
    unittest.main()
