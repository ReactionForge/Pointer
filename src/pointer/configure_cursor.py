"""Apply the cursor and keep a reversible backup of the values we change."""

from pathlib import Path
from ctypes import wintypes
import ctypes
import json
import os
import sys
import winreg
from .runtime_paths import ASSET_ROOT, DATA_ROOT

REFERENCE_ROOT = ASSET_ROOT / "reference"
CURSOR = REFERENCE_ROOT / "reference-black-arrow.cur"
CURSORS = {
    "Arrow": CURSOR,
    "IBeam": REFERENCE_ROOT / "reference-black-ibeam.cur",
    "Wait": REFERENCE_ROOT / "reference-black-busy.ani",
    "AppStarting": REFERENCE_ROOT / "reference-black-working.ani",
    "Hand": REFERENCE_ROOT / "reference-black-hand.cur",
    "Help": REFERENCE_ROOT / "reference-black-help.cur",
    "Crosshair": REFERENCE_ROOT / "reference-black-crosshair.cur",
    "NWPen": REFERENCE_ROOT / "reference-black-pen.cur",
    "No": REFERENCE_ROOT / "reference-black-no.cur",
    "SizeNS": REFERENCE_ROOT / "reference-black-ns.cur",
    "SizeWE": REFERENCE_ROOT / "reference-black-ew.cur",
    "SizeNWSE": REFERENCE_ROOT / "reference-black-nwse.cur",
    "SizeNESW": REFERENCE_ROOT / "reference-black-nesw.cur",
    "SizeAll": REFERENCE_ROOT / "reference-black-move.cur",
    "UpArrow": REFERENCE_ROOT / "reference-black-up.cur",
    "Pin": REFERENCE_ROOT / "reference-black-pin.cur",
    "Person": REFERENCE_ROOT / "reference-black-person.cur",
}
ADAPTIVE_CURSORS = {
    role: ASSET_ROOT / "legacy-invert" / path.name.replace("reference-black-", "adaptive-")
    for role, path in CURSORS.items()
}
BACKUP = DATA_ROOT / "original-cursor-settings.json"
KEY_PATH = r"Control Panel\Cursors"
SCHEME_PATH = KEY_PATH + r"\Schemes"
SCHEME_NAME = "Screenshot Black Arrow"
ADAPTIVE_SCHEME_NAME = "Screenshot Adaptive Contrast"
CHANGED_VALUES = ("", *CURSORS, "Scheme Source")
ROLES = ("Arrow", "Help", "AppStarting", "Wait", "Crosshair", "IBeam", "NWPen", "No", "SizeNS", "SizeWE", "SizeNWSE", "SizeNESW", "SizeAll", "UpArrow", "Hand", "Pin", "Person")
USER32 = ctypes.WinDLL("user32", use_last_error=True)
USER32.LoadImageW.argtypes = (wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT)
USER32.LoadImageW.restype = wintypes.HANDLE
USER32.DestroyCursor.argtypes = (wintypes.HANDLE,)
USER32.SystemParametersInfoW.argtypes = (wintypes.UINT, wintypes.UINT, ctypes.c_void_p, wintypes.UINT)
USER32.SystemParametersInfoW.restype = wintypes.BOOL
USER32.SetSystemCursor.argtypes = (wintypes.HANDLE, wintypes.DWORD)
USER32.SetSystemCursor.restype = wintypes.BOOL


def read_values(path):
    values = {}
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            for i in range(winreg.QueryInfoKey(key)[1]):
                name, value, kind = winreg.EnumValue(key, i)
                if not isinstance(value, (str, int, list)):
                    continue
                values[name] = {"value": value, "type": kind}
    except FileNotFoundError:
        pass
    return values


def restore_value(key, name, entry):
    if entry is None:
        try:
            winreg.DeleteValue(key, name)
        except FileNotFoundError:
            pass
    else:
        winreg.SetValueEx(key, name, 0, entry["type"], entry["value"])


def validate_backup(value):
    """Reject incomplete backups before original settings can be overwritten."""
    if not isinstance(value, dict) or not isinstance(value.get("cursor_values"), dict):
        raise ValueError("Invalid cursor backup: cursor_values is missing")
    if "previous_named_scheme" not in value:
        raise ValueError("Invalid cursor backup: previous_named_scheme is missing")
    entries = list(value["cursor_values"].values()) + [value["previous_named_scheme"]]
    additional = value.get("additional_named_schemes", {})
    if not isinstance(additional, dict):
        raise ValueError("Invalid named scheme backup")
    entries.extend(additional.values())
    for entry in entries:
        if entry is not None and (not isinstance(entry, dict) or
                                  not isinstance(entry.get("type"), int) or
                                  "value" not in entry):
            raise ValueError("Invalid registry value in cursor backup")
    return value


def save_backup(value):
    validate_backup(value)
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    temporary = BACKUP.with_name(BACKUP.name + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, BACKUP)


def restore_values(backup):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
        for name in CHANGED_VALUES:
            restore_value(key, name, backup["cursor_values"].get(name))
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, SCHEME_PATH, 0, winreg.KEY_SET_VALUE) as key:
        restore_value(key, backup.get("scheme_name", SCHEME_NAME), backup["previous_named_scheme"])
        for name, entry in backup.get("additional_named_schemes", {}).items():
            restore_value(key, name, entry)


def reload_cursors():
    ctypes.set_last_error(0)
    if not USER32.SystemParametersInfoW(0x0057, 0, None, 0x0002):
        raise ctypes.WinError(ctypes.get_last_error())
    values = read_values(KEY_PATH)
    person_path = values.get("Person", {}).get("value", "") or str(Path(os.environ["SystemRoot"]) / "Cursors" / "aero_person.cur")
    person = USER32.LoadImageW(None, os.path.expandvars(person_path), 2, 0, 0, 0x0010 | 0x0040)
    if not person:
        raise ctypes.WinError(ctypes.get_last_error())
    if not USER32.SetSystemCursor(person, 32672):
        raise ctypes.WinError(ctypes.get_last_error())


def apply(adaptive=False, dual=False):
    if dual:
        from .contrast_theme import theme_paths
        cursors = theme_paths("light")
    else:
        cursors = ADAPTIVE_CURSORS if adaptive else CURSORS
    scheme_name = ADAPTIVE_SCHEME_NAME if adaptive or dual else SCHEME_NAME
    for path in cursors.values():
        if not path.is_file():
            raise FileNotFoundError(path)
        cursor = USER32.LoadImageW(None, str(path), 2, 32, 32, 0x0010)
        if not cursor:
            raise ctypes.WinError(ctypes.get_last_error())
        USER32.DestroyCursor(cursor)
    current = read_values(KEY_PATH)
    previous_scheme = read_values(SCHEME_PATH).get(scheme_name)
    immediate_backup = {"cursor_values": current, "previous_named_scheme": previous_scheme, "scheme_name": scheme_name}
    if not BACKUP.exists():
        save_backup(immediate_backup)
    else:
        original_backup = validate_backup(json.loads(BACKUP.read_text(encoding="utf-8")))
        additional = original_backup.setdefault("additional_named_schemes", {})
        if scheme_name != original_backup.get("scheme_name", SCHEME_NAME) and scheme_name not in additional:
            additional[scheme_name] = previous_scheme
            save_backup(original_backup)
    paths = [str(cursors[role]) if role in cursors else current.get(role, {}).get("value", "") for role in ROLES]
    try:
        with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, SCHEME_PATH, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, scheme_name, 0, winreg.REG_SZ, ",".join(paths))
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY_PATH, 0, winreg.KEY_SET_VALUE) as key:
            for role, path in cursors.items():
                winreg.SetValueEx(key, role, 0, winreg.REG_SZ, str(path))
            winreg.SetValueEx(key, "", 0, winreg.REG_SZ, scheme_name)
            winreg.SetValueEx(key, "Scheme Source", 0, winreg.REG_DWORD, 1)
        reload_cursors()
    except Exception:
        restore_values(immediate_backup)
        reload_cursors()
        raise
    for role, path in cursors.items():
        print(f"Applied {role}: {path}")
    print(f"Original settings saved: {BACKUP}")


def restore():
    if not BACKUP.is_file():
        raise FileNotFoundError(BACKUP)
    restore_values(validate_backup(json.loads(BACKUP.read_text(encoding="utf-8"))))
    reload_cursors()
    print("Original cursor settings restored.")


if __name__ == "__main__":
    from .adaptive_switcher import stop, enable_startup, disable_startup, start
    stop()
    if "--restore" in sys.argv:
        disable_startup()
        restore()
    elif "--dual" in sys.argv:
        apply(dual=True)
        try:
            enable_startup()
            start()
        except Exception:
            disable_startup()
            reload_cursors()
            raise
    else:
        disable_startup()
        apply(adaptive="--adaptive" in sys.argv)
