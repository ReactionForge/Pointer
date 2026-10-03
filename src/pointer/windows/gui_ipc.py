"""Coordinate one settings window and graceful installer requests without Qt."""
import ctypes
import json
import time
import uuid
from pointer.paths import DATA_ROOT
from pointer.cursor.settings import _write_json
from .engine import INSTANCE, KERNEL32, WAIT_OBJECT_0, WAIT_ABANDONED, WAIT_TIMEOUT, SYNCHRONIZE, MUTEX_MODIFY_STATE, EVENT_MODIFY_STATE

MUTEX = rf'Local\PointerGUI_{INSTANCE}_Mutex'
ACTIVATE = rf'Local\PointerGUI_{INSTANCE}_Activate'
REQUEST = DATA_ROOT / 'gui-upgrade-request.json'
REPLY = DATA_ROOT / 'gui-upgrade-reply.json'


class WindowInstance:
    def __init__(self):
        ctypes.set_last_error(0)
        self.mutex = KERNEL32.CreateMutexW(None, True, MUTEX)
        if not self.mutex:
            raise ctypes.WinError(ctypes.get_last_error())
        self.primary = ctypes.get_last_error() != 183
        self.event = KERNEL32.CreateEventW(None, True, False, ACTIVATE)
        if not self.event:
            KERNEL32.CloseHandle(self.mutex)
            raise ctypes.WinError(ctypes.get_last_error())
        if not self.primary:
            KERNEL32.SetEvent(self.event)

    def activation_requested(self):
        if KERNEL32.WaitForSingleObject(self.event,0) == WAIT_OBJECT_0:
            KERNEL32.ResetEvent(self.event)
            return True
        return False

    def close(self):
        KERNEL32.CloseHandle(self.event)
        if self.primary:
            KERNEL32.ReleaseMutex(self.mutex)
        KERNEL32.CloseHandle(self.mutex)


def prepare_gui_upgrade():
    mutex = KERNEL32.OpenMutexW(SYNCHRONIZE | MUTEX_MODIFY_STATE, False, MUTEX)
    if not mutex:
        return
    try:
        if KERNEL32.WaitForSingleObject(mutex,0) in (WAIT_OBJECT_0,WAIT_ABANDONED):
            KERNEL32.ReleaseMutex(mutex)
            return
        token = uuid.uuid4().hex
        _write_json(REQUEST, {'token':token})
        deadline = time.monotonic()+8
        while time.monotonic()<deadline:
            try:
                reply = json.loads(REPLY.read_text(encoding='utf-8'))
                if reply.get('token') == token and not reply.get('ready'):
                    raise RuntimeError(reply.get('error','请先关闭设置窗口'))
            except (FileNotFoundError,ValueError):
                pass
            if KERNEL32.WaitForSingleObject(mutex,50) in (WAIT_OBJECT_0,WAIT_ABANDONED):
                KERNEL32.ReleaseMutex(mutex)
                return
        raise RuntimeError('设置窗口未退出，升级已中止')
    finally:
        KERNEL32.CloseHandle(mutex)
