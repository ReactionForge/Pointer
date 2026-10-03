"""Canonical role renderers and click hotspots."""
from .arrow import render, render_ibeam
from .hand import render_hand
from .roles import ASSETS, render_extra

RENDERERS = {
    "arrow": (render, (3, 3)),
    "ibeam": (render_ibeam, (16, 16)),
    "hand": (render_hand, (14, 3)),
    **{kind: (lambda size, kind=kind: render_extra(size, kind), hotspot) for kind, (_, hotspot) in ASSETS.items()},
}

