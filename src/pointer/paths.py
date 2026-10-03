"""Resolve program resources and persistent user data independently."""
from dataclasses import dataclass
from pathlib import Path
import os
import sys

@dataclass(frozen=True)
class RuntimePaths:
    root: Path
    install_root: Path
    data_root: Path

def resolve_paths(root, local_app_data, frozen):
    root, local_app_data = Path(root).resolve(), Path(local_app_data).resolve()
    installed = root if frozen and root.name.casefold() == "app" and root.parent.name.casefold() == "pointer" else local_app_data / "Pointer" / "app"
    data = installed.parent / "data" if frozen else root / ".local" / "data"
    return RuntimePaths(root, installed, data)

FROZEN = bool(getattr(sys, "frozen", False))
ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[2]
_LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
_paths = resolve_paths(ROOT, _LOCAL_APP_DATA, FROZEN)
INSTALL_ROOT, DATA_ROOT = _paths.install_root, _paths.data_root
ASSET_ROOT = ROOT / "assets" / "cursors"
WEB_ROOT = ROOT / "web" / "cursor-test"
PREVIEW_ROOT = ROOT / "docs" / "images"
