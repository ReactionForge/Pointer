"""Encode the existing silhouettes as native Windows AND/XOR cursors."""

from pathlib import Path
import struct

from PIL import Image, ImageFilter

from create_cursor import SIZES, ANIMATION_FRAMES, render, render_ibeam, render_loading, riff_chunk
from create_hand_cursor import render_hand
from create_extra_cursors import ASSETS, render_extra

ROOT = Path(__file__).resolve().parent
DESTINATION = ROOT / "adaptive"


def adaptive_planes(image, mode="body"):
    """Use a black outline around the inverted body, with open interior details."""
    silhouette = image.getchannel("A").point(lambda value: 255 if value >= 128 else 0)
    radius = max(1, round(image.width / 64))
    expanded = silhouette.filter(ImageFilter.MaxFilter(radius * 2 + 1))
    inset_radius = max(1, round(image.width / 32 * 1.5))
    interior = silhouette.filter(ImageFilter.MinFilter(inset_radius * 2 + 1)).load()
    colors = Image.new("RGB", image.size)
    mask = Image.new("1", image.size, 1)
    source, shape, outer = image.load(), silhouette.load(), expanded.load()
    color_pixels, mask_pixels = colors.load(), mask.load()
    for y in range(image.height):
        for x in range(image.width):
            if shape[x, y]:
                r, g, b, _ = source[x, y]
                if mode == "body" and max(r, g, b) < 80:
                    color_pixels[x, y] = (255, 255, 255)
                elif mode == "body":
                    # Interior finger lines and symbols reveal the background,
                    # so they stay dark on dark surfaces and light on light ones.
                    color_pixels[x, y] = (0, 0, 0)
                    mask_pixels[x, y] = 1 if interior[x, y] else 0
                else:
                    color_pixels[x, y] = (r, g, b)
                    mask_pixels[x, y] = 0
            elif outer[x, y]:
                if mode == "outline":
                    color_pixels[x, y] = (255, 255, 255)
                else:
                    color_pixels[x, y] = (0, 0, 0)
                    mask_pixels[x, y] = 0
    return colors, mask


def xor_dib(image, mode="body"):
    colors, mask = adaptive_planes(image, mode)
    size = image.width
    color_stride = ((size * 24 + 31) // 32) * 4
    mask_stride = ((size + 31) // 32) * 4
    pixels = colors.tobytes("raw", "BGR")
    color_rows, mask_rows = [], []
    for y in range(size - 1, -1, -1):
        color_rows.append(pixels[y * size * 3:(y + 1) * size * 3] + bytes(color_stride - size * 3))
        row = bytearray(mask_stride)
        for x in range(size):
            if mask.getpixel((x, y)):
                row[x // 8] |= 1 << (7 - x % 8)
        mask_rows.append(bytes(row))
    xor_pixels = b"".join(color_rows)
    header = struct.pack("<IiiHHIIiiII", 40, size, size * 2, 1, 24, 0, len(xor_pixels), 0, 0, 0, 0)
    return header + xor_pixels + b"".join(mask_rows)


def cursor_bytes(images, hotspot, mode="body"):
    bodies = [xor_dib(image, mode) for image in images]
    offset, entries = 6 + 16 * len(images), []
    for image, body in zip(images, bodies):
        size = image.width
        dimension = size if size < 256 else 0
        x, y = (round(value * size / 32) for value in hotspot)
        entries.append(struct.pack("<BBBBHHII", dimension, dimension, 0, 0, x, y, len(body), offset))
        offset += len(body)
    return struct.pack("<HHH", 0, 2, len(images)) + b"".join(entries) + b"".join(bodies)


def animation_bytes(with_arrow, mode="body"):
    hotspot = (3, 3) if with_arrow else (16, 16)
    frames = [riff_chunk(b"icon", cursor_bytes([render_loading(size, frame, with_arrow) for size in SIZES[:3]], hotspot, mode)) for frame in range(ANIMATION_FRAMES)]
    header = struct.pack("<9I", 36, ANIMATION_FRAMES, ANIMATION_FRAMES, 0, 0, 24, 1, 3, 1)
    content = b"ACON" + riff_chunk(b"anih", header) + riff_chunk(b"LIST", b"fram" + b"".join(frames))
    return b"RIFF" + struct.pack("<I", len(content)) + content


RENDERERS = {
    "arrow": (render, (3, 3)),
    "ibeam": (render_ibeam, (16, 16)),
    "hand": (render_hand, (14, 3)),
    **{kind: (lambda size, kind=kind: render_extra(size, kind), hotspot) for kind, (_, hotspot) in ASSETS.items()},
}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("body", "outline"), default="body")
    arguments = parser.parse_args()
    destination = DESTINATION if arguments.mode == "body" else ROOT / "adaptive-outline"
    destination.mkdir(exist_ok=True)
    for kind, (renderer, hotspot) in RENDERERS.items():
        (destination / f"adaptive-{kind}.cur").write_bytes(cursor_bytes([renderer(size) for size in SIZES], hotspot, arguments.mode))
    for kind, with_arrow in (("busy", False), ("working", True)):
        (destination / f"adaptive-{kind}.ani").write_bytes(animation_bytes(with_arrow, arguments.mode))
    print(f"Created 17 native adaptive cursor roles in {destination}")


if __name__ == "__main__":
    main()
