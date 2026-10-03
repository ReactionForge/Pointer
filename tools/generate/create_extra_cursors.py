"""Build the remaining Windows cursor roles in the existing monochrome style."""

from pathlib import Path
import math
import struct

from PIL import Image, ImageDraw, ImageFont

from .create_cursor import SIZES, cursor_bytes, render as render_arrow
from .create_hand_cursor import render_hand


from pointer.runtime_paths import ASSET_ROOT, PREVIEW_ROOT

ROOT = ASSET_ROOT / "reference"
INK = (8, 8, 8, 255)
OUTLINE = (208, 210, 213, 255)
SUPERSAMPLE = 8


def rounded_contour(vertices, trim=0.65):
    contour = []
    for index, current in enumerate(vertices):
        previous = vertices[index - 1]
        following = vertices[(index + 1) % len(vertices)]
        before_length = math.dist(previous, current)
        after_length = math.dist(current, following)
        before = min(trim, before_length / 3)
        after = min(trim, after_length / 3)
        start = tuple(current[i] + (previous[i] - current[i]) * before / before_length for i in (0, 1))
        end = tuple(current[i] + (following[i] - current[i]) * after / after_length for i in (0, 1))
        for step in range(13):
            t = step / 12
            contour.append(tuple((1 - t) ** 2 * start[i] + 2 * t * (1 - t) * current[i] + t ** 2 * end[i] for i in (0, 1)))
    return contour


class Canvas:
    def __init__(self, size):
        self.size = size
        self.factor = size / 32 * SUPERSAMPLE
        self.image = Image.new("RGBA", (size * SUPERSAMPLE, size * SUPERSAMPLE))
        self.painter = ImageDraw.Draw(self.image)

    def points(self, points):
        return [tuple(round(value * self.factor) for value in point) for point in points]

    def polygon(self, points, width=2.2, trim=0.65):
        contour = self.points(rounded_contour(points, trim))
        self.painter.polygon(contour, fill=INK)
        self.painter.line(contour + [contour[0]], fill=OUTLINE, width=round(width * self.factor), joint="curve")

    def stroke(self, points, width, color, caps=True):
        scaled = self.points(points)
        self.painter.line(scaled, fill=color, width=round(width * self.factor), joint="curve")
        if caps:
            radius = width * self.factor / 2
            for x, y in (scaled[0], scaled[-1]):
                self.painter.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)

    def outlined_stroke(self, points, outer=5.4, inner=2.4):
        self.stroke(points, outer, OUTLINE)
        self.stroke(points, inner, INK)

    def ellipse(self, box, fill=INK, outline=OUTLINE, width=2.2):
        self.painter.ellipse(tuple(round(value * self.factor) for value in box), fill=fill, outline=outline, width=round(width * self.factor))

    def finish(self):
        return self.image.resize((self.size, self.size), Image.Resampling.LANCZOS)


def rotate(points, degrees):
    angle = math.radians(degrees)
    sine, cosine = math.sin(angle), math.cos(angle)
    return [(16 + (x - 16) * cosine - (y - 16) * sine, 16 + (x - 16) * sine + (y - 16) * cosine) for x, y in points]


def render_extra(size, kind):
    canvas = Canvas(size)
    if kind == "help":
        canvas.image.alpha_composite(render_arrow(size * SUPERSAMPLE))
        canvas.ellipse((17.2, 17.2, 30.4, 30.4), width=1.8)
        question = [(21.5, 21.8), (21.6, 21.1), (22.2, 20.6), (23.4, 20.4), (24.5, 20.7), (25.2, 21.4), (25.3, 22.2), (25, 22.9), (24.2, 23.5), (23.5, 24.1), (23.5, 24.9)]
        canvas.stroke(question, 1.45, OUTLINE)
        canvas.ellipse((22.7, 26.3, 24.3, 27.9), fill=OUTLINE, outline=OUTLINE, width=0)
    elif kind == "crosshair":
        canvas.outlined_stroke([(16, 4), (16, 28)])
        canvas.outlined_stroke([(4, 16), (28, 16)])
        canvas.stroke([(16, 12.5), (16, 19.5)], 2.4, INK)
    elif kind == "pen":
        canvas.polygon([(3.5, 28.5), (5.3, 21.8), (22.2, 4.9), (25, 4.9), (27.1, 7), (27.1, 9.8), (10.2, 26.7)], trim=0.45)
        canvas.stroke([(19.6, 7.5), (24.5, 12.4)], 1.5, OUTLINE)
        canvas.stroke([(5.3, 21.8), (10.2, 26.7)], 1.5, OUTLINE)
    elif kind == "no":
        canvas.ellipse((3, 3, 29, 29), fill=None, outline=OUTLINE, width=5.8)
        canvas.ellipse((4.7, 4.7, 27.3, 27.3), fill=None, outline=INK, width=2.4)
        canvas.outlined_stroke([(8.1, 23.9), (23.9, 8.1)], outer=5.8, inner=2.4)
    elif kind in ("ns", "ew", "nwse", "nesw"):
        points = [(2.5, 16), (8.5, 10), (8.5, 13.2), (23.5, 13.2), (23.5, 10), (29.5, 16), (23.5, 22), (23.5, 18.8), (8.5, 18.8), (8.5, 22)]
        canvas.polygon(rotate(points, {"ew": 0, "ns": 90, "nwse": 45, "nesw": -45}[kind]))
    elif kind == "move":
        canvas.polygon([(16, 2.5), (10.5, 8), (13.5, 8), (13.5, 13.5), (8, 13.5), (8, 10.5), (2.5, 16), (8, 21.5), (8, 18.5), (13.5, 18.5), (13.5, 24), (10.5, 24), (16, 29.5), (21.5, 24), (18.5, 24), (18.5, 18.5), (24, 18.5), (24, 21.5), (29.5, 16), (24, 10.5), (24, 13.5), (18.5, 13.5), (18.5, 8), (21.5, 8)], width=1.9, trim=0.55)
    elif kind == "up":
        canvas.polygon([(16, 3), (7.5, 12), (12.7, 12), (12.7, 27), (19.3, 27), (19.3, 12), (24.5, 12)])
    elif kind in ("pin", "person"):
        hand = render_hand(round(size * SUPERSAMPLE * 0.68))
        canvas.image.alpha_composite(hand, tuple(round(value * canvas.factor) for value in (1, 9)))
        if kind == "pin":
            points = [(25, 14), (21.1, 8.5), (20.5, 6.4), (20.9, 4.1), (22.3, 2.6), (25, 1.8), (27.7, 2.6), (29.1, 4.1), (29.5, 6.4), (28.9, 8.5)]
            canvas.polygon(points, width=1.65, trim=0.65)
            canvas.ellipse((23.5, 4.6, 26.5, 7.6), fill=OUTLINE, outline=OUTLINE, width=0)
        else:
            canvas.ellipse((21.7, 1.9, 28.3, 8.5), width=1.6)
            canvas.polygon([(20, 15), (20.6, 11.1), (22.5, 9.9), (27.5, 9.9), (29.4, 11.1), (30, 15)], width=1.6, trim=0.7)
    else:
        raise ValueError(kind)
    return canvas.finish()


ASSETS = {
    "help": ("Help", (3, 3)),
    "crosshair": ("Precision", (16, 16)),
    "pen": ("Handwriting", (4, 28)),
    "no": ("Unavailable", (16, 16)),
    "ns": ("Vertical resize", (16, 16)),
    "ew": ("Horizontal resize", (16, 16)),
    "nwse": ("Diagonal NW-SE", (16, 16)),
    "nesw": ("Diagonal NE-SW", (16, 16)),
    "move": ("Move", (16, 16)),
    "up": ("Alternate select", (16, 3)),
    "pin": ("Location select", (11, 11)),
    "person": ("Person select", (11, 11)),
}


def verify_cursor(asset, images, hotspot):
    raw = asset.read_bytes()
    assert struct.unpack_from("<HHH", raw) == (0, 2, len(SIZES))
    for index, (size, image) in enumerate(zip(SIZES, images)):
        width, height, colors, reserved, x, y, length, offset = struct.unpack_from("<BBBBHHII", raw, 6 + 16 * index)
        assert (width or 256, height or 256) == (size, size)
        assert (x, y) == tuple(round(value * size / 32) for value in hotspot)
        assert 0 <= x < size and 0 <= y < size
        assert offset + length <= len(raw)
        assert image.mode == "RGBA" and image.getbbox()


def main():
    preview = Image.new("RGBA", (1280, 540), "#f4f7fc")
    painter = ImageDraw.Draw(preview)
    font = ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 18)
    for index, (kind, (label, hotspot)) in enumerate(ASSETS.items()):
        images = [render_extra(size, kind) for size in SIZES]
        asset = ROOT / f"reference-black-{kind}.cur"
        asset.write_bytes(cursor_bytes(images, hotspot))
        verify_cursor(asset, images, hotspot)
        x, y = index % 4 * 320, index // 4 * 180
        painter.rectangle((x + 160, y, x + 319, y + 179), fill="#0d1117")
        painter.text((x + 12, y + 10), label, font=font, fill="#3b4350")
        painter.text((x + 170, y + 10), label, font=font, fill=OUTLINE)
        for offset in (0, 160):
            preview.alpha_composite(images[0], (x + offset + 20, y + 86))
            preview.alpha_composite(images[2], (x + offset + 76, y + 70))
        print(f"{kind}: {asset.name}, hotspot={hotspot}, sizes={SIZES}")
    preview.convert("RGB").save(PREVIEW_ROOT / "extra-cursors-preview.png")


if __name__ == "__main__":
    main()
