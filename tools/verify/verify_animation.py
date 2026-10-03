"""Verify that Windows can render all distinct frames of each native ANI."""

from pathlib import Path
import ctypes
from ctypes import wintypes
import hashlib
import json
import sys
from .verify_cursor import USER32, GDI32
from pointer.runtime_paths import ASSET_ROOT


class BitmapInfoHeader(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("width", wintypes.LONG), ("height", wintypes.LONG), ("planes", wintypes.WORD), ("bits", wintypes.WORD), ("compression", wintypes.DWORD), ("image_size", wintypes.DWORD), ("x", wintypes.LONG), ("y", wintypes.LONG), ("used", wintypes.DWORD), ("important", wintypes.DWORD)]


GDI32.CreateCompatibleDC.argtypes = (wintypes.HDC,)
GDI32.CreateCompatibleDC.restype = wintypes.HDC
GDI32.CreateDIBSection.argtypes = (wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD)
GDI32.CreateDIBSection.restype = wintypes.HBITMAP
GDI32.SelectObject.argtypes = (wintypes.HDC, wintypes.HANDLE)
GDI32.SelectObject.restype = wintypes.HANDLE
GDI32.DeleteDC.argtypes = (wintypes.HDC,)
USER32.DrawIconEx.argtypes = (wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.HANDLE, ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.HBRUSH, wintypes.UINT)
USER32.DrawIconEx.restype = wintypes.BOOL


def frames(handle):
    header = BitmapInfoHeader(ctypes.sizeof(BitmapInfoHeader), 64, -64, 1, 32, 0, 64 * 64 * 4, 0, 0, 0, 0)
    pointer = ctypes.c_void_p()
    dc = GDI32.CreateCompatibleDC(None)
    bitmap = GDI32.CreateDIBSection(dc, ctypes.byref(header), 0, ctypes.byref(pointer), None, 0)
    if not bitmap:
        GDI32.DeleteDC(dc)
        raise ctypes.WinError(ctypes.get_last_error())
    original = GDI32.SelectObject(dc, bitmap)
    try:
        signatures = []
        for index in range(24):
            ctypes.memset(pointer, 0, header.image_size)
            if not USER32.DrawIconEx(dc, 0, 0, handle, 64, 64, index, None, 3):
                raise ctypes.WinError(ctypes.get_last_error())
            GDI32.GdiFlush()
            signatures.append(hashlib.sha256(ctypes.string_at(pointer, header.image_size)).hexdigest())
        return signatures
    finally:
        GDI32.SelectObject(dc, original)
        GDI32.DeleteObject(bitmap)
        GDI32.DeleteDC(dc)


if __name__ == "__main__":
    results = []
    for filename, identifier in (("reference-black-busy.ani", 32514), ("reference-black-working.ani", 32650)):
        path = ASSET_ROOT / "reference" / filename
        if "--adaptive" in sys.argv:
            path = ASSET_ROOT / "legacy-invert" / filename.replace("reference-black-", "adaptive-")
        handle = USER32.LoadCursorFromFileW(str(path))
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            expected = frames(handle)
            result = {"file": path.name, "frames": len(expected), "distinct_frames": len(set(expected)), "animated": len(set(expected)) == 24}
            if "--system" in sys.argv:
                result["system_matches"] = expected == frames(USER32.LoadCursorW(None, ctypes.c_void_p(identifier)))
            results.append(result)
        finally:
            USER32.DestroyCursor(handle)
    print(json.dumps(results, indent=2))
    sys.exit(0 if all(item["animated"] and item.get("system_matches", True) for item in results) else 1)
