"""Coordinate one settings window and graceful installer requests without Qt."""
import ctypes
import json
import time
import uuid
from pointer.paths import DATA_ROOT, INSTALL_ROOT
from pointer.cursor.settings import _write_json
from .engine import _identity, KERNEL32, WAIT_OBJECT_0, WAIT_ABANDONED, WAIT_TIMEOUT, SYNCHRONIZE, MUTEX_MODIFY_STATE, EVENT_MODIFY_STATE
INSTANCE = _identity(INSTALL_ROOT,DATA_ROOT)

MUTEX = rf'Local\PointerGUI_{INSTANCE}_Mutex'
ACTIVATE = rf'Local\PointerGUI_{INSTANCE}_Activate'
REQUEST = DATA_ROOT / 'gui-upgrade-request.json'
REPLY = DATA_ROOT / 'gui-upgrade-reply.json'


def read_request():
    try:
        request=json.loads(REQUEST.read_text(encoding='utf-8'))
        if isinstance(request.get('token'),str) and 0 <= time.time()-request.get('created',0) <= 15:
            return request
    except (OSError,ValueError,TypeError,AttributeError):
        pass
    return None


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
        _write_json(REQUEST, {'token':token,'target_root':str(INSTALL_ROOT),'created':time.time()})
        deadline = time.monotonic()+8
        while time.monotonic()<deadline:
            try:
                reply = json.loads(REPLY.read_text(encoding='utf-8'))
                if reply.get('token') == token and not reply.get('ready'):
                    raise RuntimeError(reply.get('error','请先关闭设置窗口'))
                if reply.get('token') == token and reply.get('ready') and reply.get('detached'):
                    return
            except (FileNotFoundError,ValueError):
                pass
            if KERNEL32.WaitForSingleObject(mutex,50) in (WAIT_OBJECT_0,WAIT_ABANDONED):
                KERNEL32.ReleaseMutex(mutex)
                return
        raise RuntimeError('设置窗口未退出，升级已中止')
    finally:
        KERNEL32.CloseHandle(mutex)
        request=read_request()
        if request and request.get('token')==locals().get('token'):
            REQUEST.unlink(missing_ok=True)
