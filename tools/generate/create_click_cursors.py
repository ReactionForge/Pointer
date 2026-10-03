"""Build separate shrink and tilt modes around unchanged click hotspots."""

import math
from PIL import Image

from pointer.click_motion import SCALES, ANGLES
from pointer.runtime_paths import ASSET_ROOT
from .create_adaptive_cursors import RENDERERS
from .create_cursor import SIZES, cursor_bytes, render
from .create_dual_contrast import recolor


def main():
    for mode, theme in ((mode, theme) for mode in ("shrink", "tilt") for theme in ("light", "dark")):
        folder = ASSET_ROOT / "adaptive" / ("tilt" if mode == "tilt" else "click") / theme
        folder.mkdir(parents=True, exist_ok=True)
        for role in ("arrow", "hand"):
            renderer, hotspot = RENDERERS[role]
            originals = [recolor(renderer(size), theme) for size in SIZES]
            for frame in range(1, 5):
                scale = SCALES[frame] if mode == "shrink" else 1
                angle = math.radians(ANGLES[frame]) if mode == "tilt" else 0
                c, s = math.cos(angle) / scale, math.sin(angle) / scale
                images = []
                for size, image in zip(SIZES, originals):
                    if mode == "tilt" and role == "arrow":
                        images.append(recolor(render(size, press=frame / 4), theme))
                        continue
                    x, y = (round(value * size / 32) for value in hotspot)
                    # Inverse affine sampling keeps the same pixel under the hotspot.
                    transform = (c, s, x - c * x - s * y,
                                 -s, c, y + s * x - c * y)
                    if mode == "shrink":
                        # Preserve the original sampling arithmetic and frame bytes.
                        transform = (1 / scale, 0, x * (1 - 1 / scale),
                                     0, 1 / scale, y * (1 - 1 / scale))
                    images.append(image.transform(image.size, Image.Transform.AFFINE, transform,
                                                  resample=Image.Resampling.BICUBIC))
                (folder / f"{role}-{frame}.cur").write_bytes(cursor_bytes(images, hotspot))
    print("Created 16 shrink and 16 tilt frames; six DPI sizes, unchanged hotspots.")


if __name__ == "__main__":
    main()
