"""Build a Windows CUR from a small vector arrow, with DPI variants."""

from pathlib import Path
import math
import struct
from PIL import Image, ImageDraw
from .codec import cursor_bytes, write_cursor

from pointer.paths import ASSET_ROOT, PREVIEW_ROOT

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


def arrow_contour(press=0, style='sequoia'):
    if style == 'precision':
        contour = [
            (3.0, 3.0), (3.0, 25.0), (8.2, 19.8), (13.6, 26.6),
            (16.4, 24.2), (11.0, 17.4), (19.2, 17.4), (3.0, 3.0)
        ]
    elif style == 'falcon':
        contour = [
            (3.0, 3.0), (26.0, 12.0), (19.8, 15.2), (23.8, 23.2),
            (19.2, 25.0), (15.4, 17.0), (10.2, 25.6), (3.0, 3.0)
        ]
    elif style == 'pixel':
        contour = [
            (3.0, 3.0), (3.0, 23.0), (7.8, 18.2), (12.2, 26.2),
            (15.2, 24.8), (10.8, 16.8), (18.2, 16.8), (3.0, 3.0)
        ]
    else:  # sequoia (default)
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


def render(size, supersample=8, press=0, style='sequoia'):
    scale = size / 32
    factor = scale * supersample
    contour = arrow_contour(press, style=style)
    points = [(round(x * factor), round(y * factor)) for x, y in contour]
    extent = size * supersample
    arrow = Image.new("RGBA", (extent, extent))
    painter = ImageDraw.Draw(arrow)
    painter.polygon(points, fill=(8, 8, 8, 255))
    line_width = round((2.2 if style == 'precision' else (2.6 if style == 'pixel' else 3)) * factor)
    painter.line(points, fill=(208, 210, 213, 255), width=line_width, joint="curve" if style == 'sequoia' else "miter")
    if style == 'precision':
        # Delicate calibrated crosshair needle mark at inner center
        ch_len = round(2.5 * factor)
        cx, cy = round(10.5 * factor), round(14.5 * factor)
        painter.line([(cx - ch_len, cy), (cx + ch_len, cy)], fill=(208, 210, 213, 200), width=round(0.8 * factor))
        painter.line([(cx, cy - ch_len), (cx, cy + ch_len)], fill=(208, 210, 213, 200), width=round(0.8 * factor))
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
















def main():
    from .animation import write_animation, loading_preview
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
