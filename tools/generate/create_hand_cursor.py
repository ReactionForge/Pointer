"""Build the matching Windows link hand without a glow."""

from pathlib import Path

from PIL import Image, ImageDraw

from .create_cursor import SIZES, cursor_bytes

from pointer.runtime_paths import ASSET_ROOT, PREVIEW_ROOT

ROOT = ASSET_ROOT / "reference"
INK = (8, 8, 8, 255)
OUTLINE = (208, 210, 213, 255)
HOTSPOT = (14, 3)


def cubic(start, a, b, end, steps=24):
    return [
        (
            (1 - t) ** 3 * start[0]
            + 3 * (1 - t) ** 2 * t * a[0]
            + 3 * (1 - t) * t ** 2 * b[0]
            + t ** 3 * end[0],
            (1 - t) ** 3 * start[1]
            + 3 * (1 - t) ** 2 * t * a[1]
            + 3 * (1 - t) * t ** 2 * b[1]
            + t ** 3 * end[1],
        )
        for t in (i / steps for i in range(steps + 1))
    ]


def render_hand(size):
    supersample = 8
    factor = size / 32 * supersample
    image = Image.new("RGBA", (size * supersample, size * supersample))
    painter = ImageDraw.Draw(image)

    contour = [(12, 18.5), (12, 5)]
    contour += cubic((12, 5), (12, 1.4), (16.5, 1.4), (16.5, 5))
    contour += [(16.5, 12.2)]
    contour += cubic((16.5, 12.2), (16.5, 9.8), (20.5, 9.8), (20.5, 12.2))
    contour += [(20.5, 13.4)]
    contour += cubic((20.5, 13.4), (20.5, 11.1), (24, 11.1), (24, 13.4))
    contour += [(24, 14.8)]
    contour += cubic((24, 14.8), (24, 12.5), (27.5, 12.8), (27.5, 15.1))
    contour += [(27.5, 21)]
    contour += cubic((27.5, 21), (27.5, 24.8), (25.3, 26), (24.5, 28.4))
    contour += cubic((24.5, 28.4), (24.2, 29), (23.6, 29), (23, 29))
    contour += [(15.5, 29)]
    contour += cubic((15.5, 29), (14.2, 29), (13.6, 27.3), (12.4, 25.4))
    contour += [(6.9, 19.5)]
    contour += cubic((6.9, 19.5), (4.3, 16.7), (7.1, 13.7), (9.3, 15.8))
    contour += [(12, 18.5)]

    points = [(round(x * factor), round(y * factor)) for x, y in contour]
    painter.polygon(points, fill=INK)
    painter.line(points, fill=OUTLINE, width=round(1.8 * factor), joint="curve")

    for finger in (
        ((16.5, 12.2), (16.5, 18.5)),
        ((20.5, 13.4), (20.5, 19)),
        ((24, 14.8), (24, 19.5)),
    ):
        points = [tuple(round(value * factor) for value in point) for point in finger]
        painter.line(points, fill=OUTLINE, width=round(1.25 * factor))
        cap = .625 * factor
        x, y = points[-1]
        painter.ellipse((x - cap, y - cap, x + cap, y + cap), fill=OUTLINE)
    return image.resize((size, size), Image.Resampling.LANCZOS)


def main():
    images = [render_hand(size) for size in SIZES]
    asset = ROOT / "reference-black-hand.cur"
    asset.write_bytes(cursor_bytes(images, HOTSPOT))
    preview = Image.new("RGBA", (640, 240), "#f4f7fc")
    ImageDraw.Draw(preview).rectangle((320, 0, 639, 239), fill="#0d1117")
    for offset in (0, 320):
        preview.alpha_composite(images[0], (offset + 25, 105))
        preview.alpha_composite(images[2], (offset + 83, 86))
        preview.alpha_composite(images[4], (offset + 171, 50))
    preview.convert("RGB").save(PREVIEW_ROOT / "hand-preview.png")
    print(f"Created {asset}; hotspot={HOTSPOT}; sizes={SIZES}")


if __name__ == "__main__":
    main()
