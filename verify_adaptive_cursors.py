"""Verify cursor inversion with the Windows renderer, rather than an RGBA mockup."""

from pathlib import Path
import ctypes
import json

from PIL import Image, ImageDraw, ImageFont

from verify_animation import BitmapInfoHeader, USER32, GDI32
from create_adaptive_cursors import adaptive_planes, RENDERERS
from configure_cursor import USER32 as CURSOR_USER32

ROOT = Path(__file__).resolve().parent


def native_render(path, background, size=64, frame=0, handle=None):
    own_handle = handle is None
    handle = handle or CURSOR_USER32.LoadImageW(None, str(path), 2, size, size, 0x0010)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    header = BitmapInfoHeader(ctypes.sizeof(BitmapInfoHeader), size, -size, 1, 32, 0, size * size * 4, 0, 0, 0, 0)
    pointer = ctypes.c_void_p()
    dc = GDI32.CreateCompatibleDC(None)
    bitmap = GDI32.CreateDIBSection(dc, ctypes.byref(header), 0, ctypes.byref(pointer), None, 0)
    if not bitmap:
        GDI32.DeleteDC(dc)
        if own_handle:
            USER32.DestroyCursor(handle)
        raise ctypes.WinError(ctypes.get_last_error())
    original = GDI32.SelectObject(dc, bitmap)
    try:
        pixels = background.convert("RGBA").tobytes("raw", "BGRA")
        ctypes.memmove(pointer, pixels, len(pixels))
        if not USER32.DrawIconEx(dc, 0, 0, handle, size, size, frame, None, 3):
            raise ctypes.WinError(ctypes.get_last_error())
        GDI32.GdiFlush()
        return Image.frombytes("RGBA", (size, size), ctypes.string_at(pointer, len(pixels)), "raw", "BGRA").convert("RGB")
    finally:
        GDI32.SelectObject(dc, original)
        GDI32.DeleteObject(bitmap)
        GDI32.DeleteDC(dc)
        if own_handle:
            USER32.DestroyCursor(handle)


def check_static(destination):
    results = []
    backgrounds = [(0, 0, 0), (255, 255, 255), (128, 128, 128), (31, 69, 120)]
    for kind, (renderer, _) in RENDERERS.items():
        path = destination / f"adaptive-{kind}.cur"
        colors, mask = adaptive_planes(renderer(64))
        for color in backgrounds:
            actual = native_render(path, Image.new("RGB", (64, 64), color))
            if color == (0, 0, 0):
                assert {sample for count, sample in actual.getcolors(64 * 64)} == {(0, 0, 0), (255, 255, 255)}, f"{kind} has a non-black outline or non-white body on black"
            for y in range(64):
                for x in range(64):
                    xor = colors.getpixel((x, y))
                    expected = tuple(color[channel] ^ xor[channel] for channel in range(3)) if mask.getpixel((x, y)) else xor
                    if actual.getpixel((x, y)) != expected:
                        raise AssertionError(f"{kind} @ {(x, y)} on {color}: {actual.getpixel((x, y))} != {expected}")
        results.append(kind)
    return results


def preview(destination):
    backgrounds = [("浅色", (246, 247, 249)), ("深色", (16, 18, 22)), ("中灰", (128, 128, 128)), ("黑白交界", None)]
    examples = [("圆角箭头", "arrow"), ("文字选择", "ibeam"), ("链接小手", "hand"), ("四向移动", "move")]
    image = Image.new("RGB", (840, 428), "#181b20")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
    draw.text((22, 17), "原生自适应光标 · Windows 实际绘制结果", font=font, fill="#eeeef1")
    for column, (label, color) in enumerate(backgrounds):
        x = column * 210
        draw.text((x + 20, 56), label, font=font, fill="#c6c9cf")
        for row, (name, kind) in enumerate(examples):
            background = Image.new("RGB", (64, 64), color or (246, 247, 249))
            if color is None:
                ImageDraw.Draw(background).rectangle((32, 0, 63, 63), fill=(16, 18, 22))
            rendered = native_render(destination / f"adaptive-{kind}.cur", background)
            image.paste(rendered, (x + 21, 92 + row * 79))
            draw.text((x + 99, 113 + row * 79), name, font=font, fill="#c6c9cf")
    image.save(ROOT / "adaptive-preview.png")


def main():
    destination = ROOT / "adaptive"
    results = check_static(destination)
    animations = []
    for kind in ("busy", "working"):
        path = destination / f"adaptive-{kind}.ani"
        hashes = [native_render(path, Image.new("RGB", (64, 64), "#101216"), frame=frame).tobytes() for frame in range(24)]
        assert len(set(hashes)) == 24, f"{kind} lost animation frames"
        animations.append(kind)
    preview(destination)
    print(json.dumps({"static_roles": len(results), "backgrounds_checked_per_role": 4, "animated_roles": animations, "distinct_frames_per_animation": 24, "preview": str(ROOT / "adaptive-preview.png")}, ensure_ascii=True))


if __name__ == "__main__":
    main()
