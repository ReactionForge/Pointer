"""Generate multi-resolution Windows pointer.ico and assets from high-res master icon or procedural rendering."""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
SOURCE_PATH = ROOT / "assets" / "icon_master.jpg"


def render_procedural_master(size=1024):
    """Procedurally create Apple squircle icon with vibrant chromatic rainbow cursor."""
    img = Image.new("RGBA", (size, size), (255, 255, 255, 255))

    # 1. Subtle soft inner ambient tint
    ambient = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    adraw = ImageDraw.Draw(ambient)
    adraw.ellipse([size * 0.2, size * 0.2, size * 0.8, size * 0.8], fill=(245, 248, 252, 140))
    ambient = ambient.filter(ImageFilter.GaussianBlur(60))
    img = Image.alpha_composite(img, ambient)

    # 2. Key stops for chromatic rainbow gradient
    stops = [
        (0.0, (30, 80, 230)),    # Royal Blue at bottom stem
        (0.25, (0, 195, 235)),   # Cyan / Turquoise
        (0.50, (16, 215, 120)),  # Emerald Green
        (0.72, (250, 190, 20)),  # Amber Gold
        (1.0, (245, 75, 75)),    # Coral Red at top tip
    ]
    grad = Image.new("RGB", (size, size))
    pixels = grad.load()
    for y in range(size):
        for x in range(size):
            t = max(0.0, min(1.0, 1.0 - (x + y) / (2.0 * size)))
            for i in range(len(stops) - 1):
                t0, c0 = stops[i]
                t1, c1 = stops[i + 1]
                if t0 <= t <= t1:
                    f = (t - t0) / (t1 - t0)
                    r = int(c0[0] + (c1[0] - c0[0]) * f)
                    g = int(c0[1] + (c1[1] - c0[1]) * f)
                    b = int(c0[2] + (c1[2] - c0[2]) * f)
                    pixels[x, y] = (r, g, b)
                    break

    # 3. Floating Rounded Pointer Mask
    mask = Image.new("L", (size, size), 0)
    mdraw = ImageDraw.Draw(mask)
    ox, oy = size * 0.28, size * 0.24
    pts = [
        (ox, oy),
        (ox + size * 0.02, oy + size * 0.52),
        (ox + size * 0.16, oy + size * 0.40),
        (ox + size * 0.32, oy + size * 0.56),
        (ox + size * 0.42, oy + size * 0.46),
        (ox + size * 0.26, oy + size * 0.30),
        (ox + size * 0.44, oy + size * 0.28),
    ]
    mdraw.polygon(pts, fill=255)
    # Smooth round edges via slight dilation and blur
    mask = mask.filter(ImageFilter.GaussianBlur(6)).point(lambda v: 255 if v > 120 else 0)
    mask = mask.filter(ImageFilter.GaussianBlur(2))

    # Pointer with gradient
    ptr_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ptr_layer.paste(grad, (0, 0), mask)

    # 4. Subtle drop shadow behind pointer
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    s_mask = mask.filter(ImageFilter.GaussianBlur(16))
    shadow.paste((30, 45, 70, 70), (0, 10), s_mask)

    img = Image.alpha_composite(img, shadow)
    img = Image.alpha_composite(img, ptr_layer)
    return img


def generate_checkbox_asset():
    """Generate crisp antialiased white checkmark asset for UI checkboxes."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.line([(14, 32), (26, 44), (50, 18)], fill=(255, 255, 255, 255), width=7)
    img = img.resize((32, 32), Image.Resampling.LANCZOS)
    target = ROOT / "assets" / "check.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    img.save(target)
    return target


def build_icon():
    if SOURCE_PATH.exists():
        src = Image.open(SOURCE_PATH)
        crop_box = (105, 105, 919, 919)
        cropped = src.crop(crop_box)
    else:
        cropped = render_procedural_master(814)

    w, h = cropped.size

    # 4x supersampled mask for ultra-smooth antialiasing
    scale = 4
    sw, sh = w * scale, h * scale
    mask = Image.new("L", (sw, sh), 0)
    draw = ImageDraw.Draw(mask)
    r = int(sw * 0.224)
    draw.rounded_rectangle([0, 0, sw - 1, sh - 1], radius=r, fill=255)
    mask = mask.resize((w, h), Image.Resampling.LANCZOS)

    rgba = cropped.convert("RGBA")
    rgba.putalpha(mask)

    target_dim = 1024
    canvas = Image.new("RGBA", (target_dim, target_dim), (0, 0, 0, 0))
    icon_size = int(target_dim * 0.88)
    inset_x = (target_dim - icon_size) // 2
    inset_y = (target_dim - icon_size) // 2

    resized = rgba.resize((icon_size, icon_size), Image.Resampling.LANCZOS)

    # Soft ambient drop shadow
    shadow_mask = Image.new("L", (icon_size * scale, icon_size * scale), 0)
    sdraw = ImageDraw.Draw(shadow_mask)
    sdraw.rounded_rectangle(
        [0, 0, icon_size * scale - 1, icon_size * scale - 1],
        radius=int(icon_size * scale * 0.224),
        fill=90,
    )
    shadow_mask = shadow_mask.resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    shadow = Image.new("RGBA", (icon_size, icon_size), (15, 20, 30, 0))
    shadow.putalpha(shadow_mask)

    shadow_canvas = Image.new("RGBA", (target_dim, target_dim), (0, 0, 0, 0))
    shadow_canvas.paste(shadow, (inset_x, inset_y + 10), shadow)
    shadow_canvas = shadow_canvas.filter(ImageFilter.GaussianBlur(16))

    canvas.paste(shadow_canvas, (0, 0), shadow_canvas)
    canvas.paste(resized, (inset_x, inset_y), resized)

    # Output paths
    assets_dir = ROOT / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    canvas.save(assets_dir / "pointer.png")

    sizes = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    pkg_ico = ROOT / "packaging" / "windows" / "pointer.ico"
    canvas.save(pkg_ico, format="ICO", sizes=sizes)

    root_ico = ROOT / "pointer.ico"
    canvas.save(root_ico, format="ICO", sizes=sizes)

    dist_ico = ROOT / "dist" / "Pointer" / "pointer.ico"
    if dist_ico.parent.exists():
        canvas.save(dist_ico, format="ICO", sizes=sizes)

    generate_checkbox_asset()
    print(f"Generated {pkg_ico} and {root_ico} with sizes {sizes}")


if __name__ == "__main__":
    build_icon()
