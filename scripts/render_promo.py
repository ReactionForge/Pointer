"""Reproducible, non-destructive Pointer launch film (actual UI + renderer).

No desktop capture, registry writes, update requests or fabricated Apply success.
Uses installed Pillow/PySide6 and a separately installed FFmpeg executable.
"""
from __future__ import annotations

import argparse
from dataclasses import replace
from functools import lru_cache
import hashlib
import io
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import Mock
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from PIL import Image, ImageDraw, ImageFont
from pointer.cursor.settings import CursorSettings
from pointer.cursor.resources import RenderRequest, render_cursor
from pointer.cursor.motion import ClickMotion

DURATION = 50
SCENES = (
    (0, 6, '让每一次指向，都清晰一点。', 'A clearer cursor. A more personal desktop.'),
    (6, 14, '浅色、深色，都看得清。', 'Adaptive contrast for light and dark backgrounds.'),
    (14, 24, '你的桌面，你的光标。', 'Preview shape, color and size before applying.'),
    (24, 32, '点击，也有轻巧的回应。', 'Press, hold, release. Adjustable click motion.'),
    (32, 42, '先预览，再应用。随时回到原样。', 'Local settings. Original cursor backup. Pause and restore.'),
    (42, 50, '从一个小细节，重新喜欢你的桌面。', 'Try Pointer for Windows 10 / 11 x64.'),
)
BG = '#101319'
WHITE = '#f4f5f7'
MUTED = '#aeb6c5'
ACCENT = '#bad4f7'


def scene_at(t):
    return next((i for i, (start, end, *_rest) in enumerate(SCENES) if start <= t < end), len(SCENES) - 1)


def subtitle_text():
    def stamp(s):
        return f'{s // 3600:02d}:{s // 60 % 60:02d}:{s % 60:02d},000'
    return '\n\n'.join(f'{i+1}\n{stamp(a)} --> {stamp(b)}\n{zh}\n{en}'
                       for i, (a, b, zh, en) in enumerate(SCENES)) + '\n'


def font_path(custom=None):
    candidates = [custom] if custom else []
    candidates += [Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/msyh.ttc',
                   Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/simhei.ttf']
    for path in candidates:
        if path and Path(path).is_file():
            return str(path)
    raise RuntimeError('Pass --font with a locally licensed CJK font; fonts are not redistributed.')


def capture_ui(output):
    """Render the shipped window class with all destructive operations blocked."""
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from scripts.capture_material_ui import SafeMaterialWindow
    from scripts.safe_preview import isolated_update_services
    from PySide6.QtCore import Qt, QBuffer, QByteArray, QIODevice
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication
    output.mkdir(parents=True, exist_ok=True)
    with isolated_update_services():
        app = QApplication.instance() or QApplication([])
        backend = Mock()
        backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        backend.runtime_status.return_value = {'running': False, 'startup_enabled': False}
        backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        operations = ('apply', 'pause', 'resume', 'restore', 'set_startup', 'save',
                      'prewarm', 'prewarm_isolated', 'prewarm_resources')
        for name in operations:
            getattr(backend, name).side_effect = RuntimeError('Promo preview blocks system operations')
        window = SafeMaterialWindow(backend, policy={'supported': False, 'reason': 'isolated render'})
        window.status_timer.stop()
        window._prewarm_timer.stop()
        window.resize(1180, 800)
        window.show()
        window.preview.timer.stop()
        result = {}
        for page, index in (('appearance', 0), ('motion', 1), ('tests', 2), ('settings', 3)):
            window.select_page(index)
            app.processEvents()
            app.processEvents()
            window.preview.refresh()
            for surface in window.preview.surfaces:
                surface.grab()
            app.processEvents()
            snapshot = QImage(window.size(), QImage.Format.Format_ARGB32_Premultiplied)
            snapshot.fill(Qt.GlobalColor.transparent)
            window.render(snapshot)
            data = QByteArray()
            buffer = QBuffer(data)
            buffer.open(QIODevice.OpenModeFlag.WriteOnly)
            if not snapshot.save(buffer, 'PNG'):
                raise RuntimeError('Failed to render UI')
            image = Image.open(io.BytesIO(bytes(data))).convert('RGBA')
            image.save(output / f'app-{page}.png')
            result[page] = image
        window.close()
        for name in operations:
            getattr(backend, name).assert_not_called()
        return result


@lru_cache(maxsize=384)
def sprite(role='arrow', theme='dark', frame=0, extent=260, style='sequoia', motion='tilt'):
    settings = CursorSettings(size=64, style=style, motion=motion, auto_check_update=False)
    image, _ = render_cursor(RenderRequest(settings, role, theme, frame, 384))
    neutral, _ = render_cursor(RenderRequest(settings, role, theme, 0, 384))
    box = neutral.getchannel('A').getbbox()
    margin = 55
    box = (max(0, box[0]-margin), max(0, box[1]-margin),
           min(image.width, box[2]+margin), min(image.height, box[3]+margin))
    image = image.crop(box)
    image.thumbnail((extent, extent), Image.Resampling.LANCZOS)
    return image


def place(base, image, center):
    base.paste(image, (round(center[0]-image.width/2), round(center[1]-image.height/2)), image)


class Film:
    def __init__(self, size, font, ui):
        self.width, self.height = size
        self.vertical = self.height > self.width
        self.font = font
        self.ui = ui
        self.plates = [self.plate(i) for i in range(len(SCENES))]

    @lru_cache(maxsize=64)
    def face(self, size):
        return ImageFont.truetype(self.font, size)

    def text(self, image, xy, value, size=36, color=WHITE, anchor=None):
        ImageDraw.Draw(image).text(xy, value, font=self.face(size), fill=color, anchor=anchor)

    def wrap(self, image, xy, value, size, max_width, color=WHITE):
        lines = []
        for paragraph in value.split('\n'):
            line = ''
            for char in paragraph:
                if self.face(size).getlength(line + char) > max_width and line:
                    lines.append(line)
                    line = char
                else:
                    line += char
            lines.append(line)
        for i, line in enumerate(lines):
            self.text(image, (xy[0], xy[1] + i * (size + 18)), line, size, color)

    def card(self, image, box, fill='#1d222b'):
        ImageDraw.Draw(image).rounded_rectangle(box, radius=30, fill=fill, outline='#343d4b', width=2)

    def ui_card(self, image, page):
        if self.vertical:
            box = (60, 620, 1020, 1280)
        else:
            box = (570, 265, 1840, 950)
        self.card(image, box)
        shot = self.ui[page].copy()
        shot.thumbnail((box[2]-box[0]-20, box[3]-box[1]-20), Image.Resampling.LANCZOS)
        place(image, shot, ((box[0]+box[2])/2, (box[1]+box[3])/2))

    def plate(self, index):
        w, h = self.width, self.height
        image = Image.new('RGB', (w, h), BG)
        draw = ImageDraw.Draw(image)
        # Restrained concentric geometry; no stock imagery, fake OS chrome or logos.
        for radius in (420, 660, 900):
            cx, cy = (w//2, h//2) if self.vertical else (w*3//4, h//2)
            draw.ellipse((cx-radius, cy-radius, cx+radius, cy+radius), outline='#1b212b', width=2)
        self.text(image, (64, 40), 'POINTER', 28, ACCENT)
        self.text(image, (w-64, 42), '1.3.0-beta.6', 23, MUTED, 'ra')
        zh, en = SCENES[index][2:]
        if self.vertical:
            headline = zh.replace('从一个小细节，', '从一个小细节，\n') if index == 5 else zh
            self.wrap(image, (64, 165), headline, 61, w-128)
            self.wrap(image, (64, 380), en, 30, w-128, MUTED)
        else:
            self.text(image, (80, 126), zh, 64)
            self.text(image, (84, 220), en, 29, MUTED)
        self.text(image, (64, h-104), '真实界面隔离渲染 · 光标放大演示 · 非系统录屏', 22, MUTED)
        self.text(image, (64, h-68), 'Windows 10 / 11 x64   |   github.com/ReactionForge/Pointer', 21, MUTED)
        if index == 0:
            self.text(image, (w//2, 530 if self.vertical else 400), 'Pointer', 122, WHITE, 'mm')
            self.text(image, (w//2, 1530 if self.vertical else 895), '黑白对比  /  圆润动效  /  可恢复', 34, ACCENT, 'mm')
        elif index == 1:
            if self.vertical:
                boxes = [(70, 620, 1010, 1090), (70, 1120, 1010, 1590)]
            else:
                boxes = [(100, 350, 930, 895), (970, 350, 1800, 895)]
            for theme, box in zip(('light', 'dark'), boxes):
                self.card(image, box, '#eef0f5' if theme == 'light' else '#242a34')
                self.text(image, (box[0]+32, box[1]+22), '浅色背景' if theme == 'light' else '深色背景', 30,
                          '#4e5969' if theme == 'light' else MUTED)
        elif index == 2:
            self.ui_card(image, 'appearance')
            x, y = (70, 1400) if self.vertical else (84, 370)
            for j, value in enumerate(('造型 · 配色 · 大小', '深浅双预览', '草稿不立即改变系统')):
                self.text(image, (x, y + j*92), value, 35, ACCENT)
        elif index == 3:
            for j, label in enumerate(('箭头倾斜', '小手跟随')):
                box = ((70, 600+j*490, 1010, 1050+j*490) if self.vertical
                       else (100+j*870, 350, 910+j*870, 910))
                self.card(image, box)
                self.text(image, (box[0]+32, box[1]+25), label, 36, ACCENT)
            self.text(image, (w//2, 1650 if self.vertical else 950), '使用项目原始 ClickMotion 与光标绘图逻辑', 27, MUTED, 'mm')
        elif index == 4:
            self.ui_card(image, 'tests')
            x, y = (70, 1400) if self.vertical else (84, 350)
            for j, value in enumerate(('17 种系统光标', '原光标备份 / 暂停 / 恢复', '核心功能无需联网')):
                self.text(image, (x, y+j*90), value, 30, ACCENT)
            self.text(image, (70, 1710) if self.vertical else (84, 890), '自绘光标可能不受影响', 25, MUTED)
        else:
            x, y = (70, 700) if self.vertical else (100, 390)
            self.text(image, (x, y), '下载 Pointer', 76)
            self.text(image, (x, y+120), 'Windows 10 / 11 x64', 43, ACCENT)
            self.text(image, (x, y+220), 'EXE 安装包 / ZIP 便携分发', 32, MUTED)
            self.wrap(image, (x, y+330), 'github.com/ReactionForge/Pointer', 35, w-2*x, ACCENT)
            self.text(image, (x, y+440), '欢迎 Star、分享、反馈兼容性', 32)
            self.text(image, (x, y+520), '预发行 · 未代码签名 · 商业授权待核实', 26, MUTED)
        return image

    def frame(self, t):
        index = scene_at(t)
        image = self.plates[index].copy()
        local = t - SCENES[index][0]
        w, h = self.width, self.height
        if index == 0:
            place(image, sprite(extent=330), (w//2+14*math.sin(t*.9), 1050 if self.vertical else 660))
        elif index == 1:
            if self.vertical:
                centers = [(540+150*math.sin(local*.8), 870), (540+150*math.sin(local*.8), 1370)]
            else:
                centers = [(515+170*math.sin(local*.8), 650), (1385+170*math.sin(local*.8), 650)]
            for theme, center in zip(('light', 'dark'), centers):
                place(image, sprite(theme=theme, extent=280), center)
        elif index == 2:
            styles = ('sequoia', 'quill', 'facet', 'lance', 'droplet')
            style = styles[min(4, int(local/2))]
            center = (880, 1430) if self.vertical else (310, 770)
            place(image, sprite(style=style, extent=200), center)
        elif index == 3:
            # Reset a true motion engine per cycle; step at the film sample rate.
            phase = local % 2
            engine = ClickMotion()
            frame = 0
            for step in range(int(phase*30)+1):
                now = step/30
                frame = engine.update(.25 <= now < 1.15, now)
            for j, role in enumerate(('arrow', 'hand')):
                center = ((540, 830+j*490) if self.vertical else (505+j*870, 630))
                place(image, sprite(role=role, frame=frame, extent=290), center)
                self.text(image, (center[0], center[1]+170), '按住' if .25 <= phase < 1.15 else '松开 / 回正', 29, MUTED, 'mm')
        elif index == 5:
            place(image, sprite(extent=260), (820, 570) if self.vertical else (1590, 620))
        # Modest fade, no strobing; retain readable text for most of each shot.
        start, end = SCENES[index][:2]
        fade = min(1.0, (t-start)/.28, (end-t)/.28)
        if fade < 1:
            image = Image.blend(Image.new('RGB', image.size, BG), image, max(0, fade))
        draw = ImageDraw.Draw(image)
        draw.rectangle((0, h-4, round(w*t/DURATION), h), fill=ACCENT)
        return image


def synth_audio(path, duration=DURATION):
    """Original procedural ambient sound, no sampled recording or music library."""
    from array import array
    rate = 24000
    samples = array('h')
    chords = ((130.8128, 164.8138, 195.9977), (110, 130.8128, 164.8138),
              (87.3071, 110, 130.8128), (97.9989, 123.4708, 146.8324))
    for i in range(rate*duration):
        t = i/rate
        chord = chords[int(t/4) % len(chords)]
        p = (t % 4)/4
        env = min(1, p*14, (1-p)*14)
        value = sum(math.sin(2*math.pi*f*t)*.028 + math.sin(2*math.pi*f*2*t)*.007 for f in chord)*env
        # Delicate synthesized pulse, not a commercial stock soundtrack.
        beat = t % .5
        value += .025 * math.sin(2*math.pi*880*t)*math.exp(-beat*35)
        value *= min(1, t/2, (duration-t)/3)
        samples.append(round(max(-.95, min(.95, value))*32767))
    if sys.byteorder != 'little':
        samples.byteswap()
    with wave.open(str(path), 'wb') as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(samples.tobytes())


def encode(film, path, audio, ffmpeg, fps=30, seconds=DURATION):
    command = [ffmpeg, '-y', '-hide_banner', '-loglevel', 'error', '-f', 'rawvideo', '-pixel_format', 'rgb24',
               '-video_size', f'{film.width}x{film.height}', '-framerate', str(fps), '-i', '-', '-i', str(audio),
               '-map', '0:v:0', '-map', '1:a:0', '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
               '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '160k', '-movflags', '+faststart',
               '-t', str(seconds), str(path)]
    log_path = path.with_suffix('.ffmpeg.log')
    with log_path.open('wb') as log:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=log)
        try:
            for i in range(round(seconds*fps)):
                process.stdin.write(film.frame(i/fps).tobytes())
                if i % (fps*10) == 0:
                    print(f'{path.name}: {i/fps:.0f}/{seconds}s', flush=True)
            process.stdin.close()
            code = process.wait()
        except BaseException:
            if process.stdin and not process.stdin.closed:
                process.stdin.close()
            process.terminate()
            process.wait()
            raise
    if code:
        raise RuntimeError(f'FFmpeg exit {code}: {log_path.read_text(encoding="utf8", errors="replace")}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'dist/promo')
    parser.add_argument('--media', type=Path, default=ROOT/'docs/media')
    parser.add_argument('--ffmpeg', default=shutil.which('ffmpeg'))
    parser.add_argument('--font')
    parser.add_argument('--stills-only', action='store_true')
    parser.add_argument('--format', choices=('both', 'landscape', 'portrait'), default='both')
    args = parser.parse_args()
    if not args.stills_only and not args.ffmpeg:
        parser.error('Install FFmpeg on D: and pass --ffmpeg; do not bundle its binaries in Git.')
    args.output.mkdir(parents=True, exist_ok=True)
    args.media.mkdir(parents=True, exist_ok=True)
    ui = capture_ui(args.media)
    font = font_path(args.font)
    wide = Film((1920, 1080), font, ui)
    portrait = Film((1080, 1920), font, ui)
    wide.frame(3).save(args.media/'cover.png')
    portrait.frame(3).save(args.media/'cover-portrait.png')
    wide.frame(27).save(args.media/'motion-still.png')
    (args.media/'pointer-demo.zh-en.srt').write_text(subtitle_text(), encoding='utf8')
    # Small animated README preview, not the full film.
    preview = [wide.frame(24+i/10).resize((768, 432), Image.Resampling.LANCZOS) for i in range(30)]
    preview[0].save(args.media/'click-motion.gif', save_all=True, append_images=preview[1:], duration=100, loop=0)
    generated_videos = []
    generated_formats = {}
    ffmpeg_version = None
    if not args.stills_only:
        ffmpeg_version = subprocess.check_output([args.ffmpeg, '-version'], text=True).splitlines()[0]
        with tempfile.TemporaryDirectory(prefix='pointer-promo-', dir=args.output) as temp:
            audio = Path(temp)/'soundtrack.wav'
            synth_audio(audio)
            for layout, film in (('landscape', wide), ('portrait', portrait)):
                if args.format in ('both', layout):
                    video = args.output/f'Pointer-v1.3.0-beta.6-demo-{layout}.mp4'
                    encode(film, video, audio, args.ffmpeg)
                    generated_videos.append(video)
                    generated_formats[layout] = [film.width, film.height]
    source_files = sorted((ROOT/'src/pointer').rglob('*.py')) + [Path(__file__).resolve(),
                    ROOT/'scripts/capture_material_ui.py', ROOT/'scripts/safe_preview.py']
    source_digest = hashlib.sha256()
    for source in source_files:
        source_digest.update(source.relative_to(ROOT).as_posix().encode('utf8'))
        source_digest.update(source.read_bytes())
    manifest = {
        'version': (ROOT/'VERSION').read_text().strip(),
        'source_snapshot_sha256': source_digest.hexdigest(),
        'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'python_version': sys.version.split()[0],
        'pillow_version': __import__('PIL').__version__,
        'pyside6_version': __import__('PySide6').__version__,
        'font_filename': Path(font).name,
        'font_sha256': hashlib.sha256(Path(font).read_bytes()).hexdigest(),
        'ffmpeg_version': ffmpeg_version,
        'invocation': 'stills-only' if args.stills_only else args.format,
        'provenance': 'video entries describe only files encoded in this invocation',
        'duration_seconds': DURATION, 'fps': 30, 'frames_per_video': DURATION*30,
        'formats': generated_formats,
        'codecs': ['H.264 yuv420p', 'AAC 24 kHz'] if generated_videos else [],
        'scenes': [{'start': a, 'end': b, 'zh': zh, 'en': en} for a, b, zh, en in SCENES],
        'ui_class': 'MaterialWindow', 'capture': 'offscreen isolated actual UI + canonical cursor renderer',
        'system_actions': 'blocked; Mock assertions verified',
        'audio': 'procedural synth in this script; no third-party samples',
        'font': 'locally installed font rasterized; font file not distributed',
        'rights': 'historical project artwork rights unconfirmed; no general commercial license granted',
        'video_files': {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                        for p in generated_videos},
    }
    # A still-only or single-format run cannot relabel old/unrelated videos.
    manifest_name = 'stills-manifest.json' if args.stills_only else f'manifest-{args.format}.json'
    (args.output/manifest_name).write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    if args.format == 'both' and not args.stills_only:
        (args.output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(args.output, flush=True)


if __name__ == '__main__':
    main()
