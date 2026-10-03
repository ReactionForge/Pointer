"""Shrink the paired arrow and hand around their unchanged click hotspots."""

from PIL import Image

from pointer.click_motion import SCALES
from pointer.runtime_paths import ASSET_ROOT
from .create_adaptive_cursors import RENDERERS
from .create_cursor import SIZES, cursor_bytes
from .create_dual_contrast import recolor


def main():
    for theme in ("light", "dark"):
        folder = ASSET_ROOT / "adaptive" / "click" / theme
        folder.mkdir(parents=True, exist_ok=True)
        for role in ("arrow", "hand"):
            renderer, hotspot = RENDERERS[role]
            originals = [recolor(renderer(size), theme) for size in SIZES]
            for frame, scale in enumerate(SCALES[1:], 1):
                images = []
                for size, image in zip(SIZES, originals):
                    x, y = (round(value * size / 32) for value in hotspot)
                    # Inverse affine sampling keeps the same pixel under the hotspot.
                    transform = (1 / scale, 0, x * (1 - 1 / scale),
                                 0, 1 / scale, y * (1 - 1 / scale))
                    images.append(image.transform(image.size, Image.Transform.AFFINE, transform,
                                                  resample=Image.Resampling.BICUBIC))
                (folder / f"{role}-{frame}.cur").write_bytes(cursor_bytes(images, hotspot))
    print("Created 16 click frames with six DPI sizes and unchanged hotspots.")


if __name__ == "__main__":
    main()
