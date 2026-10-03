"""Build a Windows CUR from a small vector arrow, with DPI variants."""

from pathlib import Path
import math
import struct
from PIL import Image, ImageDraw

from pointer.runtime_paths import ASSET_ROOT, PREVIEW_ROOT

ROOT = ASSET_ROOT / "reference"
SIZES = (32, 48, 64, 96, 128, 256)
ANIMATION_FRAMES = 24


def quadratic(start, control, end, steps=24):
    return [
        (
            (1 - t) ** 2 * start[0] + 2 * (1 - t) * t * control[0] + t ** 2 * end[0],
            (1 - t) ** 2 * start[1] + 2 * (1 - t) * t * control[1] + t ** 2 * end[1],
        )
        for t in (i / steps for i in range(steps + 1))
    ]


def arrow_contour(press=0):
    contour = quadratic((6, 3), (1.5, 1.8), (3.1, 6.1))
    contour += [(11.1, 26)]
    contour += quadratic((11.1, 26), (12.4, 29.6), (14, 26))
    contour += [(17.2, 18.4)]
    contour += quadratic((17.2, 18.4), (17.8, 16.8), (19.3, 16.2))
    contour += [(26.2, 13.7)]
    contour += quadratic((26.2, 13.7), (29.8, 11.8), (26.4, 10.5))
    contour += [(6, 3)]
    if not press:
        return contour
    # A lower pivot makes the top travel further while both lower tips follow.
    pivot_x, pivot_y = 20, 16
    angle = math.radians(-6 * press)
    c, s = math.cos(angle), math.sin(angle)
    return [(pivot_x + c * (x - pivot_x) - s * (y - pivot_y),
             pivot_y + s * (x - pivot_x) + c * (y - pivot_y)) for x, y in contour]


def render(size, supersample=8, press=0):
    scale = size / 32
    factor = scale * supersample
    contour = arrow_contour(press)
    points = [(round(x * factor), round(y * factor)) for x, y in contour]
    extent = size * supersample
    arrow = Image.new("RGBA", (extent, extent))
    painter = ImageDraw.Draw(arrow)
    painter.polygon(points, fill=(8, 8, 8, 255))
    painter.line(points, fill=(208, 210, 213, 255), width=round(3 * factor), joint="curve")
    return arrow.resize((size, size), Image.Resampling.LANCZOS)


def render_ibeam(size):
    supersample = 8
    factor = size / 32 * supersample
    image = Image.new("RGBA", (size * supersample, size * supersample))
    painter = ImageDraw.Draw(image)

    def rounded(box, radius, color):
        painter.rounded_rectangle(
            tuple(round(value * factor) for value in box),
            radius=round(radius * factor),
            fill=color,
        )

    outline = (208, 210, 213, 255)
    core = (8, 8, 8, 255)
    rounded((13, 3, 19, 29), 1.5, outline)
    rounded((9, 2, 23, 7), 1.7, outline)
    rounded((9, 25, 23, 30), 1.7, outline)
    rounded((14.5, 4, 17.5, 28), .8, core)
    rounded((10.5, 3.5, 21.5, 5.5), .8, core)
    rounded((10.5, 26.5, 21.5, 28.5), .8, core)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def render_loading(size, frame, with_arrow=False):
    supersample = 8
    factor = size / 32 * supersample
    extent = size * supersample
    image = render(extent, supersample=1) if with_arrow else Image.new("RGBA", (extent, extent))
    painter = ImageDraw.Draw(image)
    center, radius, outer_width, inner_width = (
        ((25, 24), 4.5, 3.5, 1.5) if with_arrow else ((16, 16), 10, 5.5, 2.5)
    )
    angle = frame * 360 / ANIMATION_FRAMES
    points = [
        (
            (center[0] + radius * math.cos(math.radians(angle + offset))) * factor,
            (center[1] + radius * math.sin(math.radians(angle + offset))) * factor,
        )
        for offset in range(271)
    ]
    for width, color in ((outer_width, (208, 210, 213, 255)), (inner_width, (8, 8, 8, 255))):
        painter.line(points, fill=color, width=round(width * factor), joint="curve")
        cap_radius = width * factor / 2
        for x, y in (points[0], points[-1]):
            painter.ellipse((x - cap_radius, y - cap_radius, x + cap_radius, y + cap_radius), fill=color)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def dib(image):
    size = image.width
    pixels = image.tobytes("raw", "BGRA")
    stride = size * 4
    bottom_up = b"".join(pixels[y * stride:(y + 1) * stride] for y in range(size - 1, -1, -1))
    mask_stride = ((size + 31) // 32) * 4
    alpha = image.getchannel("A")
    rows = []
    for y in range(size - 1, -1, -1):
        row = bytearray(mask_stride)
        for x in range(size):
            if alpha.getpixel((x, y)) == 0:
                row[x // 8] |= 1 << (7 - x % 8)
        rows.append(bytes(row))
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 32, 0, len(bottom_up), 0, 0, 0, 0)
    return header + bottom_up + b"".join(rows)


def cursor_bytes(images, hotspot):
    bodies = [dib(image) for image in images]
    offset = 6 + 16 * len(images)
    entries = []
    for image, body in zip(images, bodies):
        size = image.width
        dimension = size if size < 256 else 0
        x = round(hotspot[0] * size / 32)
        y = round(hotspot[1] * size / 32)
        entries.append(struct.pack("<BBBBHHII", dimension, dimension, 0, 0, x, y, len(body), offset))
        offset += len(body)
    return struct.pack("<HHH", 0, 2, len(images)) + b"".join(entries) + b"".join(bodies)


def write_cursor(images, filename, hotspot):
    cursor = cursor_bytes(images, hotspot)
    (ROOT / filename).write_bytes(cursor)
    print(f"Created {ROOT / filename} ({len(cursor)} bytes, {len(images)} sizes)")


def riff_chunk(tag, content):
    return tag + struct.pack("<I", len(content)) + content + (b"\0" if len(content) % 2 else b"")


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


def main():
    images = [render(size) for size in SIZES]
    write_cursor(images, "reference-black-arrow.cur", (3, 3))
    text_images = [render_ibeam(size) for size in SIZES]
    write_cursor(text_images, "reference-black-ibeam.cur", (16, 16))
    write_animation("reference-black-busy.ani", False)
    write_animation("reference-black-working.ani", True)
    loading_preview()
    images[0].save(PREVIEW_ROOT / "cursor-preview.png")
    preview = Image.new("RGBA", (320, 128), "#f4f7fc")
    ImageDraw.Draw(preview).rectangle((160, 0, 319, 127), fill="#0d1117")
    preview.alpha_composite(images[0], (25, 48))
    preview.alpha_composite(images[2], (80, 32))
    preview.alpha_composite(images[0], (185, 48))
    preview.alpha_composite(images[2], (240, 32))
    preview.convert("RGB").save(PREVIEW_ROOT / "cursor-preview-sizes.png")
    text_preview = Image.new("RGBA", (320, 128), "#f4f7fc")
    ImageDraw.Draw(text_preview).rectangle((160, 0, 319, 127), fill="#0d1117")
    text_preview.alpha_composite(images[0], (20, 48))
    text_preview.alpha_composite(text_images[0], (58, 48))
    text_preview.alpha_composite(text_images[2], (92, 32))
    text_preview.alpha_composite(images[0], (180, 48))
    text_preview.alpha_composite(text_images[0], (218, 48))
    text_preview.alpha_composite(text_images[2], (252, 32))
    text_preview.convert("RGB").save(PREVIEW_ROOT / "cursor-preview-text.png")


if __name__ == "__main__":
    main()
