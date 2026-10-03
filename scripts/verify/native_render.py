"""Render a native CUR/ANI on a supplied background without changing Windows."""
import ctypes
from PIL import Image
from .verify_animation import BitmapInfoHeader, USER32, GDI32
from pointer.windows.scheme import USER32 as CURSOR_USER32

def native_render(path, background, size=64, frame=0, handle=None):
    own_handle = handle is None
    handle = handle or CURSOR_USER32.LoadImageW(None, str(path), 2, size, size, 0x0010)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    header = BitmapInfoHeader(ctypes.sizeof(BitmapInfoHeader), size, -size, 1, 32, 0, size * size * 4, 0, 0, 0, 0)
    pointer = ctypes.c_void_p()
    dc = GDI32.CreateCompatibleDC(None)
    bitmap = GDI32.CreateDIBSection(dc, ctypes.byref(header), 0, ctypes.byref(pointer), None, 0)
    if not bitmap:
        GDI32.DeleteDC(dc)
        if own_handle:
            USER32.DestroyCursor(handle)
        raise ctypes.WinError(ctypes.get_last_error())
    original = GDI32.SelectObject(dc, bitmap)
    try:
        pixels = background.convert("RGBA").tobytes("raw", "BGRA")
        ctypes.memmove(pointer, pixels, len(pixels))
        if not USER32.DrawIconEx(dc, 0, 0, handle, size, size, frame, None, 3):
            raise ctypes.WinError(ctypes.get_last_error())
        GDI32.GdiFlush()
        return Image.frombytes("RGBA", (size, size), ctypes.string_at(pointer, len(pixels)), "raw", "BGRA").convert("RGB")
    finally:
        GDI32.SelectObject(dc, original)
        GDI32.DeleteObject(bitmap)
        GDI32.DeleteDC(dc)
        if own_handle:
            USER32.DestroyCursor(handle)

