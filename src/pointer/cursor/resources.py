"""Shared previews, native resource generation and integrity-checked user caches."""
from dataclasses import dataclass, replace
from functools import lru_cache
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import tempfile
import threading
import uuid

from PIL import Image
from .settings import CursorSettings, _write_json
from .theme import FILENAMES, theme_paths, click_paths
from .art.catalog import RENDERERS
from .art.animation import render_loading
from .art.codec import dib, riff_chunk
from pointer.paths import ASSET_ROOT

DPI_VARIANTS = (96, 144, 192, 288, 384, 768)
RENDER_VERSION = 3


@dataclass(frozen=True)
class RenderRequest:
    settings: CursorSettings
    role: str
    theme: str = 'light'
    frame: int = 0
    dpi: int = 96


@lru_cache(maxsize=2048)
def _base(role, pixels, animation_frame, style='sequoia'):
    if role in ('busy', 'working'):
        return render_loading(pixels, animation_frame, role == 'working')
    if role not in RENDERERS:
        raise ValueError(f'Unknown cursor role: {role}')
    if role == 'arrow':
        from .art.arrow import render
        return render(pixels, style=style)
    return RENDERERS[role][0](pixels)


_TONE_LUT = [max(0, min(255, round((v - 8) * 255 / 202))) for v in range(256)]


def _color(image, settings, theme):
    body = getattr(settings, theme + '_body')
    outline = getattr(settings, theme + '_outline')
    colors = [tuple(int(color[i:i + 2], 16) for i in (1, 3, 5)) for color in (body, outline)]
    tone = image.convert('L').point(_TONE_LUT)
    channels = [tone.point([round(colors[0][n] + (colors[1][n] - colors[0][n]) * v / 255) for v in range(256)]) for n in range(3)]
    colored = Image.merge('RGBA', (*channels, image.getchannel('A')))
    if getattr(settings, 'aura_glow', False):
        from PIL import ImageFilter
        aura_hex = getattr(settings, 'aura_color', '')
        if not aura_hex or len(aura_hex) != 7:
            aura_hex = outline
        glow_rgb = tuple(int(aura_hex[i:i+2], 16) for i in (1, 3, 5))
        mask = colored.getchannel('A')
        blur_rad = max(1.5, image.width / 24)
        glow_alpha = mask.filter(ImageFilter.GaussianBlur(radius=blur_rad))
        glow_alpha = glow_alpha.point(lambda v: min(150, round(v * 0.65)))
        glow_layer = Image.new('RGBA', colored.size, (*glow_rgb, 0))
        glow_layer.putalpha(glow_alpha)
        base = Image.new('RGBA', colored.size, (0, 0, 0, 0))
        base.alpha_composite(glow_layer)
        base.alpha_composite(colored)
        return base
    return colored


def canvas_size(settings, dpi=96):
    padding = math.ceil(settings.size * .4) + 2
    return round(settings.size * dpi / 96) + 2 * round(padding * dpi / 96)


def render_cursor(request):
    settings, role, theme = request.settings, request.role, request.theme
    if theme not in ('light', 'dark') or request.dpi not in DPI_VARIANTS:
        raise ValueError('Invalid theme or DPI')
    max_frame = 23 if role in ('busy', 'working') else 4
    if type(request.frame) is not int or not 0 <= request.frame <= max_frame:
        raise ValueError('Invalid animation frame')
    pixels = round(settings.size * request.dpi / 96)
    padding = round((math.ceil(settings.size * .4) + 2) * request.dpi / 96)
    style = getattr(settings, 'style', 'sequoia')
    image = _color(_base(role, pixels, request.frame if role in ('busy', 'working') else 0, style=style), settings, theme)
    canvas = Image.new('RGBA', (pixels + 2 * padding, pixels + 2 * padding))
    canvas.paste(image, (padding, padding))
    hotspot = ((3, 3) if role == 'working' else (16, 16)) if role in ('busy', 'working') else RENDERERS[role][1]
    hotspot = tuple(round(v * pixels / 32) + padding for v in hotspot)
    if role in ('arrow', 'hand') and request.frame and settings.motion != 'off' and settings.strength:
        amount = request.frame / 4 * settings.strength / 50
        motion_mode = settings.motion
        if motion_mode == 'shrink':
            scale = 1 - .1 * amount
            angle = 0
            pivot = RENDERERS[role][1]
        elif motion_mode == 'spring':
            # Underdamped harmonic bounce: frame 1 down, 2 deep, 3 overshoot rebound, 4 settle
            spring_scales = (1.0, 0.96, 0.90, 1.04, 1.00)
            target_scale = spring_scales[request.frame]
            scale = 1.0 + (target_scale - 1.0) * (settings.strength / 50)
            angle = math.radians(-3 * amount) if role == 'arrow' else 0
            pivot = (20, 16) if role == 'arrow' else RENDERERS[role][1]
        elif motion_mode == 'pulse':
            scale = 1.0
            angle = 0
            pivot = RENDERERS[role][1]
            from PIL import ImageDraw
            pulse_draw = ImageDraw.Draw(canvas)
            hx, hy = hotspot
            radius = round(amount * 10 * pixels / 32)
            if radius > 1:
                outline_color = getattr(settings, theme + '_outline')
                rgb = tuple(int(outline_color[i:i+2], 16) for i in (1, 3, 5))
                alpha = max(0, round(180 * (1 - amount)))
                pulse_draw.ellipse(
                    (hx - radius, hy - radius, hx + radius, hy + radius),
                    outline=(*rgb, alpha),
                    width=max(1, round(1.5 * request.dpi / 96))
                )
        elif motion_mode == 'trail':
            scale = 1.0
            angle = math.radians(-2 * amount)
            pivot = RENDERERS[role][1]
            from PIL import ImageDraw
            trail_draw = ImageDraw.Draw(canvas)
            offset = round(amount * 4 * pixels / 32)
            body_color = getattr(settings, theme + '_body')
            rgb = tuple(int(body_color[i:i+2], 16) for i in (1, 3, 5))
            trail_draw.polygon(
                [(hotspot[0] + offset, hotspot[1] + offset),
                 (hotspot[0] + offset + 2, hotspot[1] + offset + 5),
                 (hotspot[0] + offset + 5, hotspot[1] + offset + 2)],
                fill=(*rgb, round(100 * amount))
            )
        else:  # tilt
            scale = 1
            angle = math.radians((-6 if role == 'arrow' else -12) * amount)
            pivot = (20, 16) if role == 'arrow' and settings.motion == 'tilt' else RENDERERS[role][1]
        x, y = (v * pixels / 32 + padding for v in pivot)
        c, s = math.cos(angle) / scale, math.sin(angle) / scale
        transform = (c, s, x - c*x - s*y, -s, c, y + s*x - c*y)
        canvas = canvas.transform(canvas.size, Image.Transform.AFFINE, transform, resample=Image.Resampling.BICUBIC)
    return canvas, hotspot


def encode_cur(images_and_hotspots):
    # CUR directory entries represent raster sizes up to 256. Windows scales
    # these to the requested physical canvas size when loading a larger DPI.
    variants = {}
    for image, hotspot in images_and_hotspots:
        if image.width > 256:
            ratio = 256 / image.width
            image = image.resize((256, 256), Image.Resampling.LANCZOS)
            hotspot = tuple(round(v * ratio) for v in hotspot)
        variants[image.width] = (image, hotspot)
    images = list(variants.values())
    offset = 6 + 16 * len(images)
    entries, bodies = [], []
    for image, (x, y) in images:
        body = dib(image)
        dimension = image.width if image.width < 256 else 0
        entries.append(struct.pack('<BBBBHHII', dimension, dimension, 0, 0, x, y, len(body), offset))
        bodies.append(body)
        offset += len(body)
    return struct.pack('<HHH', 0, 2, len(images)) + b''.join(entries) + b''.join(bodies)


def _ani_frame(cursor):
    if len(cursor) < 22 or cursor[:4] != b"\0\0\2\0":
        raise ValueError("ANI frame must be a CUR resource")
    count = struct.unpack_from("<H", cursor, 4)[0]
    if not count or 6 + count * 16 > len(cursor):
        raise ValueError("Invalid CUR directory")
    index = max(range(count), key=lambda i: cursor[6 + i * 16] or 256)
    entry = cursor[6 + index * 16:22 + index * 16]
    length, offset = struct.unpack_from("<II", entry, 8)
    if offset < 6 + count * 16 or offset + length > len(cursor):
        raise ValueError("Invalid CUR frame data")
    # Windows rejects some multi-resolution ANI combinations. One high-quality
    # raster per frame loads reliably and scales to the requested physical size.
    return struct.pack("<HHH", 0, 2, 1) + entry[:12] + struct.pack("<I", 22) + cursor[offset:offset + length]


def encode_ani(frames, interval_ms=50):
    if len(frames) < 2:
        raise ValueError('ANI needs multiple frames')
    rate = max(1, round(interval_ms * 60 / 1000))
    header = struct.pack('<9I', 36, len(frames), len(frames), 0, 0, 32, 1, rate, 1)
    contents = b'ACON' + riff_chunk(b'anih', header)
    contents += riff_chunk(b'LIST', b'fram' + b''.join(riff_chunk(b'icon', _ani_frame(frame)) for frame in frames))
    return b'RIFF' + struct.pack('<I', len(contents)) + contents


@dataclass(frozen=True)
class ResourceBundle:
    key: str
    root: Path
    size: int
    settings: CursorSettings
    builtin: bool = False

    def paths(self, theme, frame=0):
        if theme not in ('light', 'dark') or frame not in range(5):
            raise ValueError('Invalid resource selection')
        if self.builtin:
            if frame and self.settings.motion != 'off':
                return click_paths(theme, frame, self.settings.motion)
            normal = theme_paths(theme)
        else:
            normal = {role: self.root / theme / ('adaptive-' + filename) for role, filename in FILENAMES.items()}
            if frame and self.settings.motion != 'off':
                return {role: self.root / theme / f'{role.lower()}-{frame}.cur' for role in ('Arrow', 'Hand')}
        return normal if not frame else {role: normal[role] for role in ('Arrow', 'Hand')}


def _render_key(settings):
    value = settings.to_dict()
    for name in ('startup', 'press_ms', 'release_ms', 'appearance', 'shake_to_find', 'game_dnd', 'tray_enabled', 'auto_check_update', 'skip_update_version'):
        value.pop(name, None)
    value['render_version'] = RENDER_VERSION
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _valid_bundle(root, key):
    try:
        manifest = json.loads((root / 'MANIFEST.json').read_text(encoding='utf-8'))
        if not isinstance(manifest, dict) or manifest.get('key') != key:
            return False
        if not isinstance(manifest.get('files'), dict) or not manifest['files']:
            return False
        for name, digest in manifest['files'].items():
            path = (root / name).resolve()
            if not path.is_relative_to(root.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                return False
        return True
    except (OSError, ValueError, KeyError, TypeError):
        return False


_RESOURCE_LOCKS = {}
_LOCKS_GUARD = threading.Lock()
_RESOURCE_LOCK = _LOCKS_GUARD


def _resource_lock_for(key):
    with _LOCKS_GUARD:
        lock = _RESOURCE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _RESOURCE_LOCKS[key] = lock
        return lock


def _generate_bundle(settings, root):
    def frames(role, theme, frame):
        return [render_cursor(RenderRequest(settings, role, theme, frame, dpi)) for dpi in DPI_VARIANTS]

    for theme in ('light', 'dark'):
        destination = root / theme
        destination.mkdir(parents=True, exist_ok=True)

    def generate_static(item):
        theme, role, filename = item
        kind = filename.split('.')[0]
        if filename.endswith('.ani'):
            content = encode_ani([encode_cur([render_cursor(RenderRequest(settings, kind, theme, f, 768))]) for f in range(24)])
        else:
            content = encode_cur(frames(kind, theme, 0))
        return (root / theme / ('adaptive-' + filename), content)

    def generate_motion(item):
        theme, role, frame = item
        return (root / theme / f'{role}-{frame}.cur', encode_cur(frames(role, theme, frame)))

    items = [(theme, role, filename) for theme in ('light', 'dark') for role, filename in FILENAMES.items()]
    motion_items = []
    if settings.motion != 'off':
        motion_items = [(theme, role, frame) for theme in ('light', 'dark') for role in ('arrow', 'hand') for frame in range(1, 5)]

    from concurrent.futures import ThreadPoolExecutor
    workers = min(8, (os.cpu_count() or 4) * 2)
    with ThreadPoolExecutor(max_workers=workers) as executor:
        for path, content in executor.map(generate_static, items):
            path.write_bytes(content)
        if motion_items:
            for path, content in executor.map(generate_motion, motion_items):
                path.write_bytes(content)


def prepare_resources(settings, cache_root):
    defaults = CursorSettings()
    geometry = ('size', 'strength', 'light_body', 'light_outline', 'dark_body', 'dark_outline', 'style', 'aura_glow', 'aura_color')
    if all(getattr(settings, name) == getattr(defaults, name) for name in geometry) and settings.motion in ('tilt', 'shrink', 'off'):
        return ResourceBundle('builtin', ASSET_ROOT / 'adaptive', 32, settings, True)
    cache_root = Path(cache_root).resolve()
    cache_root.mkdir(parents=True, exist_ok=True)
    key = _render_key(settings)
    index = cache_root / (key + '.json')
    try:
        name = json.loads(index.read_text(encoding='utf-8'))['folder']
        target = (cache_root / name).resolve()
        if target.is_relative_to(cache_root) and _valid_bundle(target, key):
            return ResourceBundle(key, target, canvas_size(settings), settings)
    except (OSError, ValueError, KeyError, TypeError):
        pass
    with _resource_lock_for(key):
        try:
            name = json.loads(index.read_text(encoding='utf-8'))['folder']
            target = (cache_root / name).resolve()
            if target.is_relative_to(cache_root) and _valid_bundle(target, key):
                return ResourceBundle(key, target, canvas_size(settings), settings)
        except (OSError, ValueError, KeyError, TypeError):
            pass
        target = cache_root / (key + '-' + uuid.uuid4().hex[:8])
        with tempfile.TemporaryDirectory(prefix='.building-', dir=cache_root) as temporary:
            working = Path(temporary).resolve()
            assert working.is_relative_to(cache_root)
            _generate_bundle(settings, working)
            files = {path.relative_to(working).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                     for path in working.rglob('*') if path.is_file()}
            _write_json(working / 'MANIFEST.json', {'key': key, 'files': files})
            if not _valid_bundle(working, key):
                raise ValueError('生成的光标资源校验失败')
            os.replace(working, target)
        _write_json(index, {'folder': target.name})
        return ResourceBundle(key, target, canvas_size(settings), settings)
