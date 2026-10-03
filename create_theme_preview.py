from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from create_cursor import render, render_ibeam, render_loading
from create_hand_cursor import render_hand
from create_extra_cursors import render_extra

ROOT = Path(__file__).resolve().parent
LABELS = [
    ("普通选择", render),
    ("文字选择", render_ibeam),
    ("加载", lambda size: render_loading(size, 0)),
    ("后台加载", lambda size: render_loading(size, 0, True)),
    ("链接小手", render_hand),
    ("帮助", lambda size: render_extra(size, "help")),
    ("精确选择", lambda size: render_extra(size, "crosshair")),
    ("手写", lambda size: render_extra(size, "pen")),
    ("禁止", lambda size: render_extra(size, "no")),
    ("上下缩放", lambda size: render_extra(size, "ns")),
    ("左右缩放", lambda size: render_extra(size, "ew")),
    ("斜向缩放 1", lambda size: render_extra(size, "nwse")),
    ("斜向缩放 2", lambda size: render_extra(size, "nesw")),
    ("移动", lambda size: render_extra(size, "move")),
    ("备用选择", lambda size: render_extra(size, "up")),
    ("位置选择", lambda size: render_extra(size, "pin")),
    ("人物选择", lambda size: render_extra(size, "person")),
]

preview = Image.new("RGBA", (960, 384), "#0d1117")
painter = ImageDraw.Draw(preview)
font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 15)
for index, (label, renderer) in enumerate(LABELS):
    column, row = index % 6, index // 6
    x, y = column * 160, row * 128
    painter.rounded_rectangle((x + 5, y + 5, x + 154, y + 122), radius=10, fill="#161c24")
    preview.alpha_composite(renderer(64), (x + 48, y + 12))
    bounds = painter.textbbox((0, 0), label, font=font)
    painter.text((x + (160 - bounds[2]) / 2, y + 89), label, font=font, fill="#d0d2d5")
preview.convert("RGB").save(ROOT / "theme-preview.png")
print(ROOT / "theme-preview.png")
