"""Inspect loaded Windows cursor pixels to verify the actual applied asset."""

from pathlib import Path
import ctypes
from ctypes import wintypes
import hashlib
import json
import sys
import winreg

ROOT = Path(__file__).resolve().parent
USER32 = ctypes.WinDLL("user32", use_last_error=True)
GDI32 = ctypes.WinDLL("gdi32", use_last_error=True)


class IconInfo(ctypes.Structure):
    _fields_ = [("icon", wintypes.BOOL), ("x", wintypes.DWORD), ("y", wintypes.DWORD), ("mask", wintypes.HBITMAP), ("color", wintypes.HBITMAP)]


class Bitmap(ctypes.Structure):
    _fields_ = [("kind", wintypes.LONG), ("width", wintypes.LONG), ("height", wintypes.LONG), ("stride", wintypes.LONG), ("planes", wintypes.WORD), ("bits_per_pixel", wintypes.WORD), ("bits", ctypes.c_void_p)]


USER32.LoadCursorW.argtypes = (wintypes.HINSTANCE, ctypes.c_void_p)
USER32.LoadCursorW.restype = wintypes.HANDLE
USER32.LoadCursorFromFileW.argtypes = (wintypes.LPCWSTR,)
USER32.LoadCursorFromFileW.restype = wintypes.HANDLE
USER32.GetIconInfo.argtypes = (wintypes.HANDLE, ctypes.POINTER(IconInfo))
USER32.GetIconInfo.restype = wintypes.BOOL
USER32.DestroyCursor.argtypes = (wintypes.HANDLE,)
GDI32.GetObjectW.argtypes = (wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p)
GDI32.GetBitmapBits.argtypes = (wintypes.HBITMAP, wintypes.LONG, ctypes.c_void_p)
GDI32.DeleteObject.argtypes = (wintypes.HANDLE,)


def signature(handle):
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    info = IconInfo()
    if not USER32.GetIconInfo(handle, ctypes.byref(info)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        digests = {}
        for name, handle in (("color", info.color), ("mask", info.mask)):
            bitmap = Bitmap()
            if not GDI32.GetObjectW(handle, ctypes.sizeof(bitmap), ctypes.byref(bitmap)):
                raise ctypes.WinError(ctypes.get_last_error())
            length = bitmap.stride * bitmap.height
            data = ctypes.create_string_buffer(length)
            if GDI32.GetBitmapBits(handle, length, data) != length:
                raise ctypes.WinError(ctypes.get_last_error())
            digests[name] = {"size": [bitmap.width, bitmap.height], "sha256": hashlib.sha256(data.raw).hexdigest()}
        return {"size": digests["color"]["size"], "hotspot": [info.x, info.y], "sha256": digests["color"]["sha256"], "mask_sha256": digests["mask"]["sha256"]}
    finally:
        GDI32.DeleteObject(info.mask)
        GDI32.DeleteObject(info.color)


if __name__ == "__main__":
    results = []
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors") as key:
        for role, filename, identifier in (
            ("Arrow", "reference-black-arrow.cur", 32512),
            ("IBeam", "reference-black-ibeam.cur", 32513),
            ("Wait", "reference-black-busy.ani", 32514),
            ("AppStarting", "reference-black-working.ani", 32650),
            ("Hand", "reference-black-hand.cur", 32649),
            ("Help", "reference-black-help.cur", 32651),
            ("Crosshair", "reference-black-crosshair.cur", 32515),
            ("NWPen", "reference-black-pen.cur", 32631),
            ("No", "reference-black-no.cur", 32648),
            ("SizeNS", "reference-black-ns.cur", 32645),
            ("SizeWE", "reference-black-ew.cur", 32644),
            ("SizeNWSE", "reference-black-nwse.cur", 32642),
            ("SizeNESW", "reference-black-nesw.cur", 32643),
            ("SizeAll", "reference-black-move.cur", 32646),
            ("UpArrow", "reference-black-up.cur", 32516),
            ("Pin", "reference-black-pin.cur", 32671),
            ("Person", "reference-black-person.cur", 32672),
        ):
            path = winreg.QueryValueEx(key, role)[0]
            expected_path = ROOT / "adaptive" / filename.replace("reference-black-", "adaptive-") if "--adaptive" in sys.argv else ROOT / filename
            disk = USER32.LoadCursorFromFileW(str(expected_path))
            try:
                expected = signature(disk)
                actual = signature(USER32.LoadCursorW(None, ctypes.c_void_p(identifier)))
                results.append({"role": role, "configured_path": path, "expected": expected, "system_cursor": actual, "matches": expected == actual and Path(path) == expected_path})
            finally:
                USER32.DestroyCursor(disk)
    output = [{"role": item["role"], "matches": item["matches"], "size": item["system_cursor"]["size"], "hotspot": item["system_cursor"]["hotspot"]} for item in results] if "--compact" in sys.argv else results
    print(json.dumps(output, ensure_ascii=True, indent=2))
    sys.exit(0 if all(result["matches"] for result in results) else 1)
