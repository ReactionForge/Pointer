"""Render real cursor families at native pixel sizes; no Windows operations."""
import argparse
import json
import sys
from pathlib import Path
from dataclasses import replace
from PIL import Image, ImageDraw, ImageFont
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from pointer.cursor.resources import RenderRequest, render_cursor, encode_cur, encode_ani
from pointer.cursor.settings import CursorSettings
from pointer.cursor.theme import FILENAMES
ROLE_IDS = tuple(name.split('.')[0] for name in FILENAMES.values())
from pointer.ui.pages.appearance import WORKSPACE_PRESETS
from pointer.cursor.art.families import RECOMMENDED_STYLES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'.local/art-direction-v2/render-review')
    parser.add_argument('--assets', action='store_true')
    parser.add_argument('--asset-root', type=Path, default=ROOT/'assets/cursors/art-v2')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf', 14)
    report = {}
    sizes = (24, 32, 48, 64)
    for style in RECOMMENDED_STYLES:
        sheet = Image.new('RGB', (840, 64+len(ROLE_IDS)*104), '#f5f5f7')
        draw = ImageDraw.Draw(sheet)
        draw.text((16, 12), style+' | native body setting / no scaling', font=font, fill='#202126')
        for col, size in enumerate(sizes):
            draw.text((130+col*176, 38), str(size)+' px', font=font, fill='#202126')
        for row, role in enumerate(ROLE_IDS):
            y = 64+row*104
            draw.text((12, y+38), role, font=font, fill='#202126')
            for col, size in enumerate(sizes):
                for index, theme in enumerate(('light', 'dark')):
                    x = 128+col*176+index*86
                    background = '#f0f1f5' if theme == 'light' else '#25262b'
                    draw.rectangle((x, y, x+83, y+99), fill=background)
                    settings = CursorSettings(style=style, size=size)
                    image, hotspot = render_cursor(RenderRequest(settings, role, theme))
                    bbox = image.getchannel('A').getbbox()
                    crop = image.crop(bbox)
                    sheet.paste(crop, (x+(84-crop.width)//2, y+(100-crop.height)//2), crop)
                    report[f'{style}/{size}/{role}/{theme}'] = {
                        'canvas_px': image.size, 'alpha_bounds_px': bbox, 'hotspot_px': hotspot,
                        'hotspot_alpha': image.getpixel(hotspot)[3],
                    }
        sheet.save(args.output/(style+'-native-sizes.png'))
        if args.assets and style != 'sequoia':
            for theme in ('light', 'dark'):
                folder = args.asset_root/style/theme
                folder.mkdir(parents=True, exist_ok=True)
                for role in ROLE_IDS:
                    animated = role in ('busy', 'working')
                    frames = [encode_cur([render_cursor(RenderRequest(CursorSettings(style=style, size=size), role, theme, frame))
                                          for size in sizes]) for frame in range(24 if animated else 1)]
                    (folder/(role+('.ani' if animated else '.cur'))).write_bytes(encode_ani(frames) if animated else frames[0])
    palette = Image.new('RGB', (1600, 620), '#f5f5f7')
    draw = ImageDraw.Draw(palette)
    for number, preset in enumerate(WORKSPACE_PRESETS):
        col, bank = number % 4, number // 4
        draw.text((col*400+12, bank*310+12), preset['id'], font=font, fill='#202126')
        for row, theme in enumerate(('light', 'dark')):
            for index, style in enumerate(RECOMMENDED_STYLES):
                x, y = col*400+index*60, bank*310+row*130+40
                draw.rectangle((x, y, x+59, y+119), fill='#f0f1f5' if theme == 'light' else '#25262b')
                settings = CursorSettings(style=style, **{k: preset[k] for k in ('light_body', 'light_outline', 'dark_body', 'dark_outline')})
                image, _ = render_cursor(RenderRequest(settings, 'arrow', theme))
                crop = image.crop(image.getchannel('A').getbbox())
                palette.paste(crop, (x+12, y+35), crop)
    palette.save(args.output/'curated-palettes-native-32.png')
    (args.output/'hotspots.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(args.output)


if __name__ == '__main__':
    main()
