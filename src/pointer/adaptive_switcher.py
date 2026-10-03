"""Switch between two local cursor themes without moving the pointer."""

from pathlib import Path
from ctypes import wintypes
import base64
import ctypes
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
import winreg

from .runtime_paths import DATA_ROOT, FROZEN, ROOT


STATUS_FILE = DATA_ROOT / "contrast-switcher-status.json"
STARTUP_BACKUP = DATA_ROOT / "contrast-switcher-startup-backup.json"
SCRIPT = Path(__file__).resolve()
INSTANCE = hashlib.sha256(str(ROOT).casefold().encode("utf-8")).hexdigest()[:16]
MUTEX_NAME = rf"Local\PointerAdaptiveContrast_{INSTANCE}_Mutex"
EVENT_NAME = rf"Local\PointerAdaptiveContrast_{INSTANCE}_Stop"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "PointerAdaptiveContrast"
CURSOR_KEY = r"Control Panel\Cursors"
WAIT_OBJECT_0, WAIT_ABANDONED, WAIT_TIMEOUT = 0, 0x80, 0x102
SYNCHRONIZE, MUTEX_MODIFY_STATE, EVENT_MODIFY_STATE = 0x100000, 1, 2
IMAGE_CURSOR, LR_LOADFROMFILE, LR_DEFAULTSIZE = 2, 0x10, 0x40
PERIOD, BACKGROUND_PERIOD = 1 / 120, .05
STABLE_SECONDS, MIN_SWITCH_SECONDS = .1, .2

USER32 = ctypes.WinDLL("user32", use_last_error=True)
GDI32 = ctypes.WinDLL("gdi32", use_last_error=True)
KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)


class POINT(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class CURSORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("flags", wintypes.DWORD),
                ("hCursor", wintypes.HANDLE), ("ptScreenPos", POINT)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", wintypes.LONG),
                ("biHeight", wintypes.LONG), ("biPlanes", wintypes.WORD),
                ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", wintypes.LONG),
                ("biYPelsPerMeter", wintypes.LONG), ("biClrUsed", wintypes.DWORD),
                ("biClrImportant", wintypes.DWORD)]


def _signature(library, name, arguments, result):
    function = getattr(library, name)
    function.argtypes, function.restype = arguments, result
    return function


_signature(KERNEL32, "CreateMutexW", [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE)
_signature(KERNEL32, "OpenMutexW", [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE)
_signature(KERNEL32, "ReleaseMutex", [wintypes.HANDLE], wintypes.BOOL)
_signature(KERNEL32, "CreateEventW", [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE)
_signature(KERNEL32, "OpenEventW", [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR], wintypes.HANDLE)
_signature(KERNEL32, "SetEvent", [wintypes.HANDLE], wintypes.BOOL)
_signature(KERNEL32, "ResetEvent", [wintypes.HANDLE], wintypes.BOOL)
_signature(KERNEL32, "WaitForSingleObject", [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD)
_signature(KERNEL32, "CloseHandle", [wintypes.HANDLE], wintypes.BOOL)
_signature(USER32, "GetCursorPos", [ctypes.POINTER(POINT)], wintypes.BOOL)
_signature(USER32, "GetCursorInfo", [ctypes.POINTER(CURSORINFO)], wintypes.BOOL)
_signature(USER32, "GetAsyncKeyState", [ctypes.c_int], ctypes.c_short)
_signature(USER32, "GetSystemMetrics", [ctypes.c_int], ctypes.c_int)
_signature(USER32, "GetDC", [wintypes.HWND], wintypes.HDC)
_signature(USER32, "ReleaseDC", [wintypes.HWND, wintypes.HDC], ctypes.c_int)
_signature(USER32, "LoadImageW", [wintypes.HINSTANCE, wintypes.LPCWSTR, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.HANDLE)
_signature(USER32, "LoadCursorFromFileW", [wintypes.LPCWSTR], wintypes.HANDLE)
_signature(USER32, "CopyImage", [wintypes.HANDLE, wintypes.UINT, ctypes.c_int, ctypes.c_int, wintypes.UINT], wintypes.HANDLE)
_signature(USER32, "DestroyCursor", [wintypes.HANDLE], wintypes.BOOL)
_signature(USER32, "SetSystemCursor", [wintypes.HANDLE, wintypes.DWORD], wintypes.BOOL)
_signature(USER32, "DrawIconEx", [wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.HANDLE, ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.HBRUSH, wintypes.UINT], wintypes.BOOL)
_signature(GDI32, "GetPixel", [wintypes.HDC, ctypes.c_int, ctypes.c_int], wintypes.DWORD)
_signature(GDI32, "CreateCompatibleDC", [wintypes.HDC], wintypes.HDC)
_signature(GDI32, "CreateDIBSection", [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD], wintypes.HBITMAP)
_signature(GDI32, "SelectObject", [wintypes.HDC, wintypes.HANDLE], wintypes.HANDLE)
_signature(GDI32, "DeleteObject", [wintypes.HANDLE], wintypes.BOOL)
_signature(GDI32, "DeleteDC", [wintypes.HDC], wintypes.BOOL)
_signature(GDI32, "GdiFlush", [], wintypes.BOOL)


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def _read_status(path=STATUS_FILE):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _scheme_name():
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CURSOR_KEY) as key:
        return winreg.QueryValueEx(key, "")[0]


def _initial_theme():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CURSOR_KEY) as key:
            path = Path(os.path.expandvars(winreg.QueryValueEx(key, "Arrow")[0]))
        return path.parent.name if path.parent.name in ("light", "dark") else None
    except (OSError, TypeError):
        return None


def _set_dpi_awareness():
    if hasattr(USER32, "SetProcessDpiAwarenessContext"):
        function = _signature(USER32, "SetProcessDpiAwarenessContext", [ctypes.c_void_p], wintypes.BOOL)
        function(ctypes.c_void_p(-4))


def _sample_luminance():
    info = CURSORINFO(cbSize=ctypes.sizeof(CURSORINFO))
    if not USER32.GetCursorInfo(ctypes.byref(info)) or not info.flags & 1:
        return None
    point = POINT()
    if not USER32.GetCursorPos(ctypes.byref(point)):
        return None
    left, top = USER32.GetSystemMetrics(76), USER32.GetSystemMetrics(77)
    right = left + USER32.GetSystemMetrics(78)
    bottom = top + USER32.GetSystemMetrics(79)
    dc = USER32.GetDC(None)
    if not dc:
        return None
    values = []
    try:
        for dx, dy in ((0, 0), (-3, 0), (3, 0), (0, -3), (0, 3)):
            x, y = point.x + dx, point.y + dy
            if not (left <= x < right and top <= y < bottom):
                continue
            color = GDI32.GetPixel(dc, x, y)
            if color != 0xFFFFFFFF:
                r, g, b = color & 255, color >> 8 & 255, color >> 16 & 255
                values.append(.2126 * r + .7152 * g + .0722 * b)
    finally:
        USER32.ReleaseDC(None, dc)
    return statistics.median(values) if values else None


def _has_animation(cursor):
    """Check that frame data survives copying; no screen pixels are captured."""
    dc = GDI32.CreateCompatibleDC(None)
    if not dc:
        raise ctypes.WinError(ctypes.get_last_error())
    bits = ctypes.c_void_p()
    header = BITMAPINFOHEADER(biSize=40, biWidth=32, biHeight=-32, biPlanes=1, biBitCount=32)
    bitmap = GDI32.CreateDIBSection(dc, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
    previous = None
    try:
        if not bitmap or not bits.value:
            raise ctypes.WinError(ctypes.get_last_error())
        previous = GDI32.SelectObject(dc, bitmap)
        rendered = []
        for frame in (0, 6):
            ctypes.memset(bits, 0, 32 * 32 * 4)
            if not USER32.DrawIconEx(dc, 0, 0, cursor, 32, 32, frame, None, 3):
                return False
            GDI32.GdiFlush()
            rendered.append(ctypes.string_at(bits, 32 * 32 * 4))
        return rendered[0] != rendered[1]
    finally:
        if previous:
            GDI32.SelectObject(dc, previous)
        if bitmap:
            GDI32.DeleteObject(bitmap)
        GDI32.DeleteDC(dc)


class _SchemeChanged(Exception):
    pass


class _CursorCache:
    def __init__(self, paths):
        self.paths = paths
        self.handles = {}
        self.reload_animations = set()
        self.notes = []
        try:
            for theme, roles in paths.items():
                for role, path in roles.items():
                    self.handles[theme, role] = self._load(path)
                    if Path(path).suffix.lower() != ".ani":
                        continue
                    original = self.handles[theme, role]
                    if not _has_animation(original):
                        raise RuntimeError(f"Animated cursor has no distinct frames: {Path(path).name}")
                    self.reload_animations.add((theme, role))
                    duplicate = USER32.CopyImage(original, IMAGE_CURSOR, 0, 0, 0)
                    try:
                        if not duplicate or not _has_animation(duplicate):
                            self.notes.append(f"{theme}/{role}: fresh LoadImageW; CopyImage did not preserve frames")
                        else:
                            self.notes.append(f"{theme}/{role}: fresh LoadImageW preserves the original ANI resource")
                    finally:
                        if duplicate:
                            USER32.DestroyCursor(duplicate)
            if not self.notes:
                self.notes.append("CopyImage verified distinct animation frames for both themes")
        except Exception:
            self.close()
            raise

    @staticmethod
    def _load(path):
        cursor = USER32.LoadImageW(None, str(path), IMAGE_CURSOR, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if not cursor:
            raise ctypes.WinError(ctypes.get_last_error())
        return cursor

    @staticmethod
    def _load_animated(path):
        return _CursorCache._load(path)

    def apply(self, theme, role_ids, scheme_name):
        prepared = []
        try:
            for role, identity in role_ids.items():
                key = theme, role
                if key in self.reload_animations:
                    cursor = self._load_animated(self.paths[theme][role])
                else:
                    cursor = USER32.CopyImage(self.handles[key], IMAGE_CURSOR, 0, 0, 0)
                    if not cursor:
                        raise ctypes.WinError(ctypes.get_last_error())
                prepared.append([identity, cursor])
            for entry in prepared:
                if _scheme_name() != scheme_name:
                    raise _SchemeChanged()
                identity, cursor = entry
                if not USER32.SetSystemCursor(cursor, identity):
                    raise ctypes.WinError(ctypes.get_last_error())
                # SetSystemCursor consumes this owned copy, never the cached template.
                entry[1] = None
        finally:
            for _, cursor in prepared:
                if cursor:
                    USER32.DestroyCursor(cursor)

    def close(self):
        for cursor in self.handles.values():
            USER32.DestroyCursor(cursor)
        self.handles.clear()


def _run():
    ctypes.set_last_error(0)
    mutex = KERNEL32.CreateMutexW(None, True, MUTEX_NAME)
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        KERNEL32.CloseHandle(mutex)
        return
    event, cache, click_cache, scheme_name = None, None, None, None
    state = {"pid": os.getpid(), "running": False, "theme": None, "switches": 0, "last_error": None}
    last_written = None

    def publish():
        nonlocal last_written
        if state != last_written:
            _atomic_json(STATUS_FILE, state)
            last_written = dict(state)

    try:
        from .contrast_theme import THEME_NAME, ROLE_IDS, choose_theme, theme_paths, click_paths
        from .click_motion import ClickMotion
        scheme_name = THEME_NAME
        event = KERNEL32.CreateEventW(None, True, False, EVENT_NAME)
        if not event:
            raise ctypes.WinError(ctypes.get_last_error())
        if not KERNEL32.ResetEvent(event):
            raise ctypes.WinError(ctypes.get_last_error())
        if _scheme_name() != scheme_name:
            raise _SchemeChanged()
        _set_dpi_awareness()
        cache = _CursorCache({theme: theme_paths(theme) for theme in ("light", "dark")})
        click_cache = _CursorCache({f"{theme}:{frame}": click_paths(theme, frame)
                                    for theme in ("light", "dark") for frame in range(5)})
        motion = ClickMotion()
        click_roles = {role: ROLE_IDS[role] for role in ("Arrow", "Hand")}
        applied_click = None
        state.update(running=True, theme=_initial_theme(), animation_copy=cache.notes,
                     click_motion=True, click_presses=0)
        publish()
        candidate, candidate_since, last_switch = None, 0, -float("inf")
        next_tick = next_background = time.monotonic()
        while True:
            if KERNEL32.WaitForSingleObject(event, 0) == WAIT_OBJECT_0:
                state["shutdown_reason"] = "stop_requested"
                break
            now = time.monotonic()
            # Button polling stays responsive; expensive pixel sampling stays at 20 Hz.
            if now >= next_background:
                next_background = now + BACKGROUND_PERIOD
                if _scheme_name() != scheme_name:
                    raise _SchemeChanged()
                luminance = _sample_luminance()
                if luminance is None:
                    candidate = None
                else:
                    requested = choose_theme(luminance, state["theme"])
                    if requested == state["theme"]:
                        candidate = None
                    elif requested != candidate:
                        candidate, candidate_since = requested, now
                    elif now - candidate_since >= STABLE_SECONDS and now - last_switch >= MIN_SWITCH_SECONDS:
                        cache.apply(requested, ROLE_IDS, scheme_name)
                        state["theme"] = requested
                        state["switches"] += 1
                        last_switch, candidate = time.monotonic(), None
                        applied_click = None
                        publish()
            # Use the reliable current-down bit, never the shared "recently pressed" bit.
            frame = motion.update(bool(USER32.GetAsyncKeyState(1) & 0x8000), now)
            click_key = f'{state["theme"]}:{frame}'
            if state["theme"] and click_key != applied_click:
                click_cache.apply(click_key, click_roles, scheme_name)
                applied_click = click_key
            if motion.presses != state["click_presses"]:
                state["click_presses"] = motion.presses
                publish()
            next_tick += PERIOD
            if next_tick < time.monotonic():
                next_tick = time.monotonic()
            wait_ms = max(1, int((next_tick - time.monotonic()) * 1000))
            KERNEL32.WaitForSingleObject(event, wait_ms)
    except _SchemeChanged:
        state["shutdown_reason"] = "user_changed_cursor_scheme"
    except Exception as error:
        state["last_error"] = f"{type(error).__name__}: {error}"
        state["shutdown_reason"] = "error"
    finally:
        # Never reload over a scheme the user selected while the helper was running.
        try:
            if state.get("shutdown_reason") == "error" and scheme_name and _scheme_name() == scheme_name:
                from .configure_cursor import reload_cursors
                reload_cursors()
        except Exception as error:
            recovery = f"Cursor reload failed: {type(error).__name__}: {error}"
            state["last_error"] = "; ".join(filter(None, (state["last_error"], recovery)))
        if cache:
            cache.close()
        if click_cache:
            click_cache.close()
        state["running"] = False
        try:
            publish()
        finally:
            if event:
                KERNEL32.CloseHandle(event)
            KERNEL32.ReleaseMutex(mutex)
            KERNEL32.CloseHandle(mutex)


def _running():
    mutex = KERNEL32.OpenMutexW(SYNCHRONIZE | MUTEX_MODIFY_STATE, False, MUTEX_NAME)
    if not mutex:
        return False
    try:
        result = KERNEL32.WaitForSingleObject(mutex, 0)
        if result in (WAIT_OBJECT_0, WAIT_ABANDONED):
            KERNEL32.ReleaseMutex(mutex)
            return False
        return result == WAIT_TIMEOUT
    finally:
        KERNEL32.CloseHandle(mutex)


def _pythonw():
    candidate = Path(sys.executable).with_name("pythonw.exe")
    return candidate if candidate.is_file() else Path(sys.executable)


def _helper_command():
    if FROZEN:
        return [str(Path(sys.executable).resolve()), "--run"]
    return [str(_pythonw()), str(ROOT / "packaging" / "windows" / "entrypoint.py"), "--run"]


def start():
    """Start a hidden, single-instance helper and return its ready status."""
    if _running():
        status = _read_status()
        if status.get("running"):
            return status
        raise RuntimeError("The cursor helper is already starting or stopping")
    environment = os.environ.copy()
    if FROZEN:
        # The helper must outlive the command that installed or started it.
        environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
    startup_info = subprocess.STARTUPINFO()
    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup_info.wShowWindow = 0
    process = subprocess.Popen(_helper_command(), cwd=ROOT, env=environment,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, creationflags=0x08000000,
                               startupinfo=startup_info)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        status = _read_status()
        if status.get("pid") == process.pid and status.get("running") and _running():
            return status
        if process.poll() is not None:
            raise RuntimeError(status.get("last_error") or status.get("shutdown_reason") or "Cursor helper exited before becoming ready")
        time.sleep(.05)
    raise RuntimeError("Cursor helper did not become ready within five seconds")


def _startup_command():
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


def stop_directory(directory):
    """Stop a helper by its resource directory without changing settings or backups.

    Migration uses the previous directory's named event instead of executing a
    command read from the registry. Missing instances are safe to ignore.
    """
    directory = Path(directory).resolve()
    identity = hashlib.sha256(str(directory).casefold().encode("utf-8")).hexdigest()[:16]
    mutex_name = rf"Local\PointerAdaptiveContrast_{identity}_Mutex"
    event_name = rf"Local\PointerAdaptiveContrast_{identity}_Stop"
    status_file = STATUS_FILE if directory == ROOT else directory / STATUS_FILE.name
    mutex = KERNEL32.OpenMutexW(SYNCHRONIZE | MUTEX_MODIFY_STATE, False, mutex_name)
    if not mutex:
        status = _read_status(status_file)
        if status.get("running"):
            status.update(running=False, shutdown_reason="not_running")
            _atomic_json(status_file, status)
        return status
    event = None
    try:
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            event = KERNEL32.OpenEventW(EVENT_MODIFY_STATE, False, event_name)
            if event:
                break
            if KERNEL32.WaitForSingleObject(mutex, 0) in (WAIT_OBJECT_0, WAIT_ABANDONED):
                KERNEL32.ReleaseMutex(mutex)
                return _read_status(status_file)
            time.sleep(.05)
        if not event:
            raise RuntimeError("Cursor helper is running but its stop event is unavailable")
        if not KERNEL32.SetEvent(event):
            raise ctypes.WinError(ctypes.get_last_error())
        result = KERNEL32.WaitForSingleObject(mutex, 7000)
        if result in (WAIT_OBJECT_0, WAIT_ABANDONED):
            KERNEL32.ReleaseMutex(mutex)
            return _read_status(status_file)
        raise RuntimeError("Cursor helper did not stop within seven seconds; no process was killed")
    finally:
        if event:
            KERNEL32.CloseHandle(event)
        KERNEL32.CloseHandle(mutex)


def stop():
    """Request graceful exit, wait for it, and remove our startup entry."""
    disable_startup()
    return stop_directory(ROOT)


if __name__ == "__main__":
    if "--run" in sys.argv:
        _run()
    elif "--stop" in sys.argv:
        result = stop()
        from .contrast_theme import THEME_NAME
        if _scheme_name() == THEME_NAME:
            from .configure_cursor import reload_cursors
            reload_cursors()
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps(start(), ensure_ascii=False))
