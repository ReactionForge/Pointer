"""Loading animation geometry and multi-frame ANI generation."""
import math, struct
from PIL import Image, ImageDraw
from pointer.paths import ASSET_ROOT, PREVIEW_ROOT
from .arrow import render, SIZES, ANIMATION_FRAMES
from .codec import riff_chunk, cursor_bytes
ROOT = ASSET_ROOT / "reference"

_ARROW_BASE_CACHE = {}


def render_loading(size, frame, with_arrow=False):
    supersample = 8
    factor = size / 32 * supersample
    extent = size * supersample
    if with_arrow:
        if extent not in _ARROW_BASE_CACHE:
            _ARROW_BASE_CACHE[extent] = render(extent, supersample=1)
        image = _ARROW_BASE_CACHE[extent].copy()
    else:
        image = Image.new("RGBA", (extent, extent))
    painter = ImageDraw.Draw(image)
    center, radius, outer_width, inner_width = (
        ((25, 24), 4.5, 3.5, 1.5) if with_arrow else ((16, 16), 10, 5.5, 2.5)
    )
    angle = frame * 360 / ANIMATION_FRAMES
    directions = [(math.cos(math.radians(angle + offset)),
                   math.sin(math.radians(angle + offset))) for offset in range(271)]
    for width, color in ((outer_width, (208, 210, 213, 255)), (inner_width, (8, 8, 8, 255))):
        # Fill a single annular contour. Thick short line segments leave radial
        # seams at their joins, which become visible in previews and at high DPI.
        points = [((center[0] + distance * dx) * factor,
                   (center[1] + distance * dy) * factor)
                  for distance, vectors in ((radius + width / 2, directions),
                                            (radius - width / 2, reversed(directions)))
                  for dx, dy in vectors]
        painter.polygon(points, fill=color)
        cap_radius = width * factor / 2
        for dx, dy in (directions[0], directions[-1]):
            x, y = (center[0] + radius * dx) * factor, (center[1] + radius * dy) * factor
            painter.ellipse((x - cap_radius, y - cap_radius, x + cap_radius, y + cap_radius), fill=color)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def write_animation(filename, with_arrow):
    hotspot = (3, 3) if with_arrow else (16, 16)
    frames = []
    for frame in range(ANIMATION_FRAMES):
        images = [render_loading(size, frame, with_arrow) for size in SIZES[:3]]
        frames.append(riff_chunk(b"icon", cursor_bytes(images, hotspot)))
    header = struct.pack("<9I", 36, ANIMATION_FRAMES, ANIMATION_FRAMES, 0, 0, 32, 1, 3, 1)
    content = b"ACON" + riff_chunk(b"anih", header) + riff_chunk(b"LIST", b"fram" + b"".join(frames))
    animation = b"RIFF" + struct.pack("<I", len(content)) + content
    (ROOT / filename).write_bytes(animation)
    print(f"Created {ROOT / filename} ({len(animation)} bytes, {ANIMATION_FRAMES} frames)")


def loading_preview():
    frames = []
    for frame in range(ANIMATION_FRAMES):
        preview = Image.new("RGBA", (320, 96), "#f4f7fc")
        ImageDraw.Draw(preview).rectangle((160, 0, 319, 95), fill="#0d1117")
        for offset in (0, 160):
            preview.alpha_composite(render_loading(32, frame), (offset + 20, 32))
            preview.alpha_composite(render_loading(64, frame, True), (offset + 80, 16))
        frames.append(preview.convert("RGB"))
    frames[0].save(PREVIEW_ROOT / "cursor-preview-loading.png")
    frames[0].save(PREVIEW_ROOT / "cursor-preview-loading.gif", save_all=True, append_images=frames[1:], duration=50, loop=0, disposal=2)
