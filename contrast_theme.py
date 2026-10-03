"""Shared paths and switching thresholds for the paired black-and-white theme."""

from runtime_paths import ROOT
THEME_NAME = "Screenshot Adaptive Contrast"
ROLE_IDS = {
    "Arrow": 32512, "IBeam": 32513, "Wait": 32514,
    "AppStarting": 32650, "Hand": 32649, "Help": 32651,
    "Crosshair": 32515, "NWPen": 32631, "No": 32648,
    "SizeNS": 32645, "SizeWE": 32644, "SizeNWSE": 32642,
    "SizeNESW": 32643, "SizeAll": 32646, "UpArrow": 32516,
    "Pin": 32671, "Person": 32672,
}
FILENAMES = dict(zip(ROLE_IDS, (
    "arrow.cur", "ibeam.cur", "busy.ani", "working.ani", "hand.cur",
    "help.cur", "crosshair.cur", "pen.cur", "no.cur", "ns.cur", "ew.cur",
    "nwse.cur", "nesw.cur", "move.cur", "up.cur", "pin.cur", "person.cur",
)))


def theme_paths(theme):
    if theme not in ("light", "dark"):
        raise ValueError(theme)
    return {role: ROOT / "dual-contrast" / theme / f"adaptive-{filename}" for role, filename in FILENAMES.items()}


def choose_theme(luminance, current=None):
    if current == "light":
        return "dark" if luminance < 112 else "light"
    if current == "dark":
        return "light" if luminance > 144 else "dark"
    return "light" if luminance >= 128 else "dark"
