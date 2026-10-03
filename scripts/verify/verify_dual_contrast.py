"""Check pure colors, native cursor copies, and freshly loaded ANI frames."""

import ctypes
import json

from PIL import Image, ImageDraw, ImageFont

from pointer.cursor.theme import ROLE_IDS, theme_paths, choose_theme
from pointer.paths import ASSET_ROOT, DATA_ROOT, PREVIEW_ROOT
from pointer.cursor.art.catalog import RENDERERS
from pointer.cursor.art.animation import render_loading
from pointer.cursor.art.palette import recolor
from .native_render import native_render
from .verify_animation import frames
from .verify_cursor import USER32, signature

USER32.CopyImage.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_int, ctypes.c_int, ctypes.c_uint)
USER32.CopyImage.restype = ctypes.c_void_p


def check_assets():
    checked, animations = 0, []
    for theme in ("light", "dark"):
        background = (238, 238, 238) if theme == "light" else (24, 24, 24)
        body = (0, 0, 0) if theme == "light" else (255, 255, 255)
        outline = tuple(255 - value for value in body)
        for kind, (renderer, _) in RENDERERS.items():
            source = renderer(64)
            path = ASSET_ROOT / "adaptive" / theme / f"adaptive-{kind}.cur"
            actual = native_render(path, Image.new("RGB", (64, 64), background))
            found_body = found_border = False
            for y in range(64):
                for x in range(64):
                    r, g, b, alpha = source.getpixel((x, y))
                    if alpha != 255:
                        continue
                    if max(r, g, b) <= 8:
                        assert actual.getpixel((x, y)) == body, (theme, kind, "body")
                        found_body = True
                    elif min(r, g, b) >= 210:
                        assert actual.getpixel((x, y)) == outline, (theme, kind, "outline")
                        found_border = True
            assert found_body and found_border, (kind, "missing color sample")
            original = USER32.LoadCursorFromFileW(str(path))
            copied = USER32.CopyImage(original, 2, 0, 0, 0)
            try:
                assert signature(original) == signature(copied), (theme, kind, "copy")
            finally:
                USER32.DestroyCursor(original)
                if copied:
                    USER32.DestroyCursor(copied)
            checked += 1
        for role in ("Wait", "AppStarting"):
            handle = USER32.LoadCursorFromFileW(str(theme_paths(theme)[role]))
            assert handle
            copied = USER32.LoadCursorFromFileW(str(theme_paths(theme)[role]))
            try:
                assert copied and copied != handle
                original_frames, copied_frames = frames(handle), frames(copied)
                assert len(set(original_frames)) == 24
                assert original_frames == copied_frames, "Fresh ANI load lost animated frames"
                animations.append(f"{theme}/{role}")
            finally:
                if copied:
                    USER32.DestroyCursor(copied)
                USER32.DestroyCursor(handle)
    assert choose_theme(100, "light") == "dark"
    assert choose_theme(160, "dark") == "light"
    assert choose_theme(128, "light") == "light"
    assert choose_theme(128, "dark") == "dark"
    return {"static_palettes_checked": checked, "pure_body_and_border": True, "animations_with_24_frames": animations}


def preview():
    image = Image.new("RGB", (840, 426), "#181b20")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 17)
    draw.text((22, 16), "黑白配对自适应 · Windows 实际绘制结果", font=font, fill="#eeeef1")
    columns = [("浅底 · 黑体白边", "light", "#E5E7EB"), ("深底 · 白体黑边", "dark", "#242830")]
    examples = [("圆角箭头", "Arrow"), ("文字选择", "IBeam"), ("链接小手", "Hand"), ("加载动画", "Wait")]
    for column, (label, theme, background) in enumerate(columns):
        x = column * 420
        draw.text((x + 22, 59), label, font=font, fill="#d0d2d5")
        for row, (label, role) in enumerate(examples):
            y = 99 + row * 78
            draw.rounded_rectangle((x + 20, y, x + 399, y + 67), radius=8, fill=background)
            tile = native_render(theme_paths(theme)[role], Image.new("RGB", (64, 64), background))
            image.paste(tile, (x + 34, y + 2))
            draw.text((x + 123, y + 23), label, font=font, fill="#15171c" if theme == "light" else "#eeeef1")
    image.save(PREVIEW_ROOT / "dual-contrast-preview.png")


def check_system(theme):
    results = []
    for role, identifier in ROLE_IDS.items():
        expected_handle = USER32.LoadCursorFromFileW(str(theme_paths(theme)[role]))
        try:
            actual_handle = USER32.LoadCursorW(None, ctypes.c_void_p(identifier))
            assert signature(expected_handle) == signature(actual_handle), (theme, role)
            if role in ("Wait", "AppStarting"):
                assert frames(expected_handle) == frames(actual_handle), (role, "animation")
            results.append(role)
        finally:
            USER32.DestroyCursor(expected_handle)
    return {"theme": theme, "system_roles_matched": len(results), "hotspots_and_animations_matched": True}


if __name__ == "__main__":
    import sys
    if "--system" in sys.argv:
        from pointer.windows.engine import _set_dpi_awareness
        _set_dpi_awareness()
        state = json.loads((DATA_ROOT / "contrast-switcher-status.json").read_text(encoding="utf-8"))
        print(json.dumps(check_system(state["theme"])))
    else:
        result = check_assets()
        preview()
        print(json.dumps(result))
