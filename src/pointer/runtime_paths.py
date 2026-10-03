"""Keep packaged cursor resources separate from the user's persistent backups."""

from pathlib import Path
import os
import sys


FROZEN = bool(getattr(sys, "frozen", False))
ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[2]
ASSET_ROOT = ROOT / "assets" / "cursors"
WEB_ROOT = ROOT / "web" / "cursor-test"
PREVIEW_ROOT = ROOT / "docs" / "images"
_LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
INSTALL_ROOT = (_LOCAL_APP_DATA / "Pointer" / "app").resolve()
# Store-hosted tools can redirect AppData writes. An installed EXE keeps its
# resolved sibling data folder when Windows starts it outside that host later.
if (FROZEN and ROOT.name.casefold() == "app" and ROOT.parent.name.casefold() == "pointer"
        and ROOT.is_relative_to(_LOCAL_APP_DATA.resolve())):
    INSTALL_ROOT = ROOT
DATA_ROOT = INSTALL_ROOT.parent / "data" if FROZEN else ROOT / ".local" / "data"
