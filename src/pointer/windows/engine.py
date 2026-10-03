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
import uuid
import winreg

from pointer.paths import ASSET_ROOT, DATA_ROOT, FROZEN, ROOT, INSTALL_ROOT


STATUS_FILE = DATA_ROOT / "contrast-switcher-status.json"
STARTUP_BACKUP = DATA_ROOT / "contrast-switcher-startup-backup.json"
CLICK_SETTINGS = DATA_ROOT / "click-motion-settings.json"
PROFILE_FILE = DATA_ROOT / "active-profile.json"
SCRIPT = Path(__file__).resolve()
def _identity(directory, data_root=None):
    text = str(Path(directory).resolve()).casefold()
    if data_root is not None:
        text += '|' + str(Path(data_root).resolve()).casefold()
    return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]


INSTANCE = _identity(ROOT, DATA_ROOT)
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

from .api import *
from .api import _signature
from .startup import enable_startup, disable_startup


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
    def __init__(self, paths, size=0):
        self.paths = paths
        self.size = size
        self.handles = {}
        self.reload_animations = set()
        self.notes = []
        try:
            for theme, roles in paths.items():
                for role, path in roles.items():
                    self.handles[theme, role] = self._load(path, size)
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
    def _load(path, size=0):
        cursor = USER32.LoadImageW(None, str(path), IMAGE_CURSOR, size, size, LR_LOADFROMFILE | (LR_DEFAULTSIZE if not size else 0))
        if not cursor:
            raise ctypes.WinError(ctypes.get_last_error())
        return cursor

    @staticmethod
    def _load_animated(path, size=0):
        return _CursorCache._load(path, size)

    def apply(self, theme, role_ids, scheme_name):
        prepared = []
        try:
            for role, identity in role_ids.items():
                key = theme, role
                if key in self.reload_animations:
                    cursor = self._load_animated(self.paths[theme][role], self.size)
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


def _read_profile(path=PROFILE_FILE):
    """Validate persisted resources before passing any file to the native loader."""
    from pointer.cursor.settings import CursorSettings, _read_json
    from pointer.cursor.theme import ROLE_IDS
    if not path.exists():
        return None
    value = _read_json(path)
    CursorSettings.from_dict(value['settings'])
    if type(value.get('size')) is not int or not 1 <= value['size'] <= 2048:
        raise ValueError('无效的光标画布尺寸')
    roots = (ASSET_ROOT.resolve(), (DATA_ROOT / 'cursor-cache').resolve())
    for field, expected in (('themes', {t: set(ROLE_IDS) for t in ('light', 'dark')}),
                            ('frames', {f'{t}:{f}': {'Arrow', 'Hand'} for t in ('light', 'dark') for f in range(5)})):
        groups = value.get(field)
        if not isinstance(groups, dict) or set(groups) != set(expected):
            raise ValueError('光标配置缺少主题或动效帧')
        for name, roles in expected.items():
            entries = groups[name]
            if not isinstance(entries, dict) or set(entries) != roles:
                raise ValueError('光标配置缺少角色')
            for role, filename in entries.items():
                resource = Path(filename).resolve()
                if not any(resource.is_relative_to(root) for root in roots) or not resource.is_file():
                    raise ValueError('光标资源不在受管理的目录中')
                entries[role] = resource
    return value


def _cursor_dpi():
    point = POINT()
    if USER32.GetCursorPos(ctypes.byref(point)) and hasattr(USER32, 'GetDpiForWindow'):
        window = _signature(USER32, 'WindowFromPoint', [POINT], wintypes.HWND)(point)
        dpi = _signature(USER32, 'GetDpiForWindow', [wintypes.HWND], wintypes.UINT)(window)
        if dpi:
            return dpi
    return 96


def _run():
    ctypes.set_last_error(0)
    mutex = KERNEL32.CreateMutexW(None, True, MUTEX_NAME)
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == 183:
        KERNEL32.CloseHandle(mutex)
        return
    event, cache, click_cache, scheme_name = None, None, None, None
    state = {"pid": os.getpid(), "running": False, "theme": None, "switches": 0, "last_error": None,
             'launch_token':os.environ.get('POINTER_LAUNCH_TOKEN'),
             'qt_loaded':any(name.startswith('PySide6') for name in sys.modules)}
    last_written = None

    def publish():
        nonlocal last_written
        if state != last_written:
            _atomic_json(STATUS_FILE, state)
            last_written = dict(state)

    try:
        from pointer.cursor.theme import THEME_NAME, ROLE_IDS, choose_theme, theme_paths, click_paths
        from pointer.cursor.motion import ClickMotion, read_mode
        scheme_name = THEME_NAME
        event = KERNEL32.CreateEventW(None, True, False, EVENT_NAME)
        if not event:
            raise ctypes.WinError(ctypes.get_last_error())
        if not KERNEL32.ResetEvent(event):
            raise ctypes.WinError(ctypes.get_last_error())
        if _scheme_name() != scheme_name:
            raise _SchemeChanged()
        _set_dpi_awareness()
        profile = _read_profile()
        settings = profile['settings'] if profile else {}
        appearance = settings.get('appearance', 'adaptive')
        click_mode = settings.get('motion', read_mode(CLICK_SETTINGS))
        normal_paths = profile['themes'] if profile else {theme: theme_paths(theme) for theme in ('light', 'dark')}
        pressed_paths = profile['frames'] if profile else {f'{theme}:{frame}': click_paths(theme, frame, click_mode)
                                                          for theme in ('light', 'dark') for frame in range(5)}
        logical_size = profile['size'] if profile else 32
        physical_size = round(logical_size * _cursor_dpi() / 96)
        cache = _CursorCache(normal_paths, size=physical_size)
        click_cache = _CursorCache(pressed_paths, size=physical_size)
        motion = ClickMotion(settings.get('press_ms', 60), settings.get('release_ms', 150))
        click_roles = {role: ROLE_IDS[role] for role in ("Arrow", "Hand")}
        applied_click = None
        initial_theme = appearance if appearance in ('light','dark') else (_initial_theme() or 'light')
        state.update(running=True, theme=initial_theme, animation_copy=cache.notes,
                     click_motion=True, click_mode=click_mode, click_presses=0)
        cache.apply(state['theme'], ROLE_IDS, scheme_name)
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
                requested_size = round(logical_size * _cursor_dpi() / 96)
                if requested_size != physical_size:
                    replacement = _CursorCache(normal_paths, size=requested_size)
                    try:
                        pressed_replacement = _CursorCache(pressed_paths, size=requested_size)
                    except Exception:
                        replacement.close()
                        raise
                    cache.close()
                    click_cache.close()
                    cache, click_cache, physical_size = replacement, pressed_replacement, requested_size
                    if state['theme']:
                        cache.apply(state['theme'], ROLE_IDS, scheme_name)
                    applied_click = None
                luminance = _sample_luminance() if appearance == 'adaptive' else (255 if appearance == 'light' else 0)
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
            frame = motion.update(bool(USER32.GetAsyncKeyState(1) & 0x8000), now) if click_mode != 'off' else 0
            click_key = f'{state["theme"]}:{frame}'
            if state["theme"] and click_key != applied_click:
                click_cache.apply(click_key, click_roles, scheme_name)
                applied_click = click_key
            if motion.presses != state["click_presses"]:
                state["click_presses"] = motion.presses
                publish()
            next_tick += PERIOD if click_mode != 'off' else BACKGROUND_PERIOD
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
            if state.get('shutdown_reason') == 'stop_requested' and click_cache and state.get('theme') and _scheme_name() == scheme_name:
                click_cache.apply(f'{state["theme"]}:0', click_roles, scheme_name)
            elif state.get("shutdown_reason") == "error" and scheme_name and _scheme_name() == scheme_name:
                from pointer.windows.scheme import reload_cursors
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
    return running_directory(ROOT, DATA_ROOT)


def running_directory(directory, data_root=None, _legacy=False):
    names = [_identity(directory,data_root)]
    if _legacy or not os.environ.get('POINTER_DATA_DIR'):
        names.append(_identity(directory))
    return any(_mutex_running(rf'Local\PointerAdaptiveContrast_{identity}_Mutex') for identity in names)


def _mutex_running(name):
    mutex = KERNEL32.OpenMutexW(SYNCHRONIZE | MUTEX_MODIFY_STATE, False, name)
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
        installed = INSTALL_ROOT/'Pointer.exe'
        executable = installed if installed.exists() else Path(sys.executable).resolve()
        return [str(executable), "--run"]
    return [str(_pythonw()), str(ROOT / "packaging" / "windows" / "entrypoint.py"), "--run"]


def start():
    """Start a hidden, single-instance helper and return its ready status."""
    if _running():
        status = _read_status()
        if status.get("running"):
            return status
        raise RuntimeError("The cursor helper is already starting or stopping")
    environment = os.environ.copy()
    token = uuid.uuid4().hex
    environment['POINTER_LAUNCH_TOKEN'] = token
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
        if status.get('launch_token') == token and status.get("running") and _running():
            return status
        if process.poll() is not None:
            raise RuntimeError(status.get("last_error") or status.get("shutdown_reason") or "Cursor helper exited before becoming ready")
        time.sleep(.05)
    raise RuntimeError("Cursor helper did not become ready within five seconds")








def stop_directory(directory, data_root=None, _legacy=False):
    """Stop a helper by its resource directory without changing settings or backups.

    Migration uses the previous directory's named event instead of executing a
    command read from the registry. Missing instances are safe to ignore.
    """
    directory = Path(directory).resolve()
    data_root = Path(data_root) if data_root is not None else (DATA_ROOT if directory == ROOT else directory.parent / 'data')
    identity = _identity(directory, None if _legacy else data_root)
    mutex_name = rf"Local\PointerAdaptiveContrast_{identity}_Mutex"
    event_name = rf"Local\PointerAdaptiveContrast_{identity}_Stop"
    status_file = data_root / STATUS_FILE.name
    mutex = KERNEL32.OpenMutexW(SYNCHRONIZE | MUTEX_MODIFY_STATE, False, mutex_name)
    if not mutex:
        if not _legacy and not os.environ.get('POINTER_DATA_DIR'):
            return stop_directory(directory, data_root, _legacy=True)
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
        from pointer.cursor.theme import THEME_NAME
        if _scheme_name() == THEME_NAME:
            from pointer.windows.scheme import reload_cursors
            reload_cursors()
        print(json.dumps(result, ensure_ascii=False))
    else:
        print(json.dumps(start(), ensure_ascii=False))
