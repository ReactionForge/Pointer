"""Typed Windows API declarations shared by the cursor service."""
import ctypes
from ctypes import wintypes

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


