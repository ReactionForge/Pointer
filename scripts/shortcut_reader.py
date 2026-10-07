"""Read saved shortcut metadata through the Unicode COM interface, without resolving it."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import uuid


class _GUID(ctypes.Structure):
    _fields_ = [('data1', wintypes.DWORD), ('data2', wintypes.WORD),
                ('data3', wintypes.WORD), ('data4', wintypes.BYTE * 8)]


def _guid(value):
    return _GUID.from_buffer_copy(uuid.UUID(value).bytes_le)


def _method(pointer, slot, arguments, result=ctypes.c_long):
    table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return ctypes.WINFUNCTYPE(result, ctypes.c_void_p, *arguments)(table[slot])


def _check(result, operation):
    if result & 0x80000000:
        raise OSError(f'{operation} failed: HRESULT 0x{result & 0xffffffff:08X}')


def read_shortcut(path):
    """Return the saved target and explicit icon location; never Save or Resolve the link."""
    ole = ctypes.WinDLL('ole32', use_last_error=True)
    ole.CoInitialize.argtypes, ole.CoInitialize.restype = [ctypes.c_void_p], ctypes.c_long
    ole.CoUninitialize.argtypes, ole.CoUninitialize.restype = [], None
    ole.CoCreateInstance.argtypes = [ctypes.POINTER(_GUID), ctypes.c_void_p, wintypes.DWORD,
                                    ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)]
    ole.CoCreateInstance.restype = ctypes.c_long
    initialized = ole.CoInitialize(None)
    # An existing apartment is usable, but its initialization belongs to the caller.
    if (initialized & 0xffffffff) != 0x80010106:  # RPC_E_CHANGED_MODE
        _check(initialized, 'CoInitialize')
    shell, persist = ctypes.c_void_p(), ctypes.c_void_p()
    try:
        clsid = _guid('00021401-0000-0000-c000-000000000046')
        shell_iid = _guid('000214f9-0000-0000-c000-000000000046')  # IShellLinkW
        persist_iid = _guid('0000010b-0000-0000-c000-000000000046')
        _check(ole.CoCreateInstance(ctypes.byref(clsid), None, 1, ctypes.byref(shell_iid),
                                    ctypes.byref(shell)), 'CoCreateInstance(IShellLinkW)')
        if not shell:
            raise OSError('CoCreateInstance returned no IShellLinkW interface')
        _check(_method(shell, 0, [ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p)])(
            shell, ctypes.byref(persist_iid), ctypes.byref(persist)), 'QueryInterface(IPersistFile)')
        if not persist:
            raise OSError('QueryInterface returned no IPersistFile interface')
        # STGM_READ | STGM_SHARE_DENY_WRITE: load only, including a Unicode link filename.
        _check(_method(persist, 5, [wintypes.LPCWSTR, wintypes.DWORD])(
            persist, str(Path(path).resolve()), 0x20), 'IPersistFile.Load')
        target, icon, index = ctypes.create_unicode_buffer(32768), ctypes.create_unicode_buffer(32768), ctypes.c_int()
        result = _method(shell, 3, [wintypes.LPWSTR, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD])(
            shell, target, len(target), None, 4)  # SLGP_RAWPATH; no search, tracking or update.
        _check(result, 'IShellLinkW.GetPath')
        if result != 0 or not target.value:
            raise OSError('IShellLinkW.GetPath returned no saved target')
        _check(_method(shell, 16, [wintypes.LPWSTR, ctypes.c_int, ctypes.POINTER(ctypes.c_int)])(
            shell, icon, len(icon), ctypes.byref(index)), 'IShellLinkW.GetIconLocation')
        return {'target': target.value, 'icon': f'{icon.value},{index.value}'}
    finally:
        for pointer in (persist, shell):
            if pointer:
                _method(pointer, 2, [], wintypes.ULONG)(pointer)
        if initialized in (0, 1):
            ole.CoUninitialize()
