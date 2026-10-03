"""Build smooth pure black/white cursor pairs for light and dark backgrounds."""

import struct

from PIL import Image

from contrast_theme import ROOT, theme_paths
from create_adaptive_cursors import RENDERERS
from create_cursor import SIZES, ANIMATION_FRAMES, render_loading, cursor_bytes, riff_chunk


def recolor(image, theme):
    tone = image.convert("L").point(lambda value: max(0, min(255, round((value - 8) * 255 / 202))))
    if theme == "dark":
        tone = tone.point(lambda value: 255 - value)
    return Image.merge("RGBA", (tone, tone, tone, image.getchannel("A")))


def animation(theme, with_arrow):
    frames = []
    for frame in range(ANIMATION_FRAMES):
        images = [recolor(render_loading(size, frame, with_arrow), theme) for size in SIZES[:3]]
        frames.append(riff_chunk(b"icon", cursor_bytes(images, (3, 3) if with_arrow else (16, 16))))
    header = struct.pack("<9I", 36, ANIMATION_FRAMES, ANIMATION_FRAMES, 0, 0, 32, 1, 3, 1)
    content = b"ACON" + riff_chunk(b"anih", header) + riff_chunk(b"LIST", b"fram" + b"".join(frames))
    return b"RIFF" + struct.pack("<I", len(content)) + content


def main():
    for theme in ("light", "dark"):
        folder = ROOT / "dual-contrast" / theme
        folder.mkdir(parents=True, exist_ok=True)
        for kind, (renderer, hotspot) in RENDERERS.items():
            images = [recolor(renderer(size), theme) for size in SIZES]
            (folder / f"adaptive-{kind}.cur").write_bytes(cursor_bytes(images, hotspot))
        theme_paths(theme)["Wait"].write_bytes(animation(theme, False))
        theme_paths(theme)["AppStarting"].write_bytes(animation(theme, True))
    print("Created 17 smooth cursor roles in each of the light and dark palettes.")


if __name__ == "__main__":
    main()
