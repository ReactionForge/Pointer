"""Resolve program resources and persistent user data independently."""
from dataclasses import dataclass
from pathlib import Path
import os
import sys
import json

INSTALLATION_MARKER = 'INSTALLATION.json'

def is_installed(root):
    """The local deployment marker contains no machine-specific paths."""
    path = Path(root) / INSTALLATION_MARKER
    if not path.exists():
        return False
    if path.stat().st_size > 1024:
        raise ValueError('安装标识损坏')
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
    except (OSError,ValueError) as error:
        raise ValueError('安装标识损坏') from error
    if value != {'schema_version':1,'data_directory':'../data'}:
        raise ValueError('安装标识损坏')
    return True

@dataclass(frozen=True)
class RuntimePaths:
    root: Path
    install_root: Path
    data_root: Path

def resolve_paths(root, local_app_data, frozen):
    root, local_app_data = Path(root).resolve(), Path(local_app_data).resolve()
    installed = root if frozen and (is_installed(root) or (root.name.casefold() == "app" and root.parent.name.casefold() == "pointer")) else local_app_data / "Pointer" / "app"
    data = installed.parent / "data" if frozen else root / ".local" / "data"
    return RuntimePaths(root, installed, data)

FROZEN = bool(getattr(sys, "frozen", False))
ROOT = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parents[2]
_LOCAL_APP_DATA = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
_paths = resolve_paths(ROOT, _LOCAL_APP_DATA, FROZEN)
INSTALL_ROOT, DATA_ROOT = _paths.install_root, _paths.data_root
INSTALL_ROOT = Path(os.environ.get('POINTER_INSTALL_DIR', INSTALL_ROOT)).resolve()
DATA_ROOT = Path(os.environ.get('POINTER_DATA_DIR', DATA_ROOT)).resolve()
ASSET_ROOT = ROOT / "assets" / "cursors"
WEB_ROOT = ROOT / "web" / "cursor-test"
PREVIEW_ROOT = ROOT / "docs" / "images"
