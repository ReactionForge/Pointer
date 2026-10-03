"""Idempotent current-user login startup registration."""
import base64, json, subprocess, winreg
from pointer.paths import DATA_ROOT
from pointer.cursor.motion import atomic_json as _atomic_json
STARTUP_BACKUP = DATA_ROOT / "contrast-switcher-startup-backup.json"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "PointerAdaptiveContrast"

def _startup_command():
    from .engine import _helper_command
    return subprocess.list2cmdline(_helper_command())


def enable_startup():
    """Write the Run value only when it changes, preserving any previous value."""
    command = _startup_command()
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
        backup = json.loads(STARTUP_BACKUP.read_text(encoding="utf-8")) if STARTUP_BACKUP.exists() else None
        try:
            value, kind = winreg.QueryValueEx(key, RUN_VALUE)
            previous = {"value": base64.b64encode(value).decode("ascii") if isinstance(value, bytes) else value,
                        "type": kind, "binary": isinstance(value, bytes)}
        except FileNotFoundError:
            value, kind, previous = None, None, None
        # Rewriting an identical value can prompt startup protection again.
        if value == command and kind == winreg.REG_SZ:
            return {"startup_enabled": True, "value_name": RUN_VALUE, "changed": False}
        if not backup or value != backup.get("installed_command"):
            backup = {"value_name": RUN_VALUE, "previous": previous}
        backup["installed_command"] = command
        _atomic_json(STARTUP_BACKUP, backup)
        winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)
    return {"startup_enabled": True, "value_name": RUN_VALUE, "changed": True}


def disable_startup():
    """Restore this Run value only if it still points to our helper."""
    backup = json.loads(STARTUP_BACKUP.read_text(encoding="utf-8")) if STARTUP_BACKUP.exists() else None
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_QUERY_VALUE | winreg.KEY_SET_VALUE) as key:
            try:
                current = winreg.QueryValueEx(key, RUN_VALUE)[0]
            except FileNotFoundError:
                return {"startup_enabled": False}
            expected = backup["installed_command"] if backup else _startup_command()
            if current != expected:
                return {"startup_enabled": False, "preserved_changed_run_value": True}
            previous = backup.get("previous") if backup else None
            if previous is None:
                winreg.DeleteValue(key, RUN_VALUE)
            else:
                value = base64.b64decode(previous["value"]) if previous.get("binary") else previous["value"]
                winreg.SetValueEx(key, RUN_VALUE, 0, previous["type"], value)
    except FileNotFoundError:
        pass
    return {"startup_enabled": False}

