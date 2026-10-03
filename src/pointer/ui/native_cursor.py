"""Use shared Windows cursor handles on owned test widgets only."""
import ctypes
from ctypes import wintypes
from PySide6.QtCore import QAbstractNativeEventFilter
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication
from pointer.cursor.theme import ROLE_IDS, FILENAMES
from pointer.windows.api import USER32, _signature

ROLE_NAMES = {PathName.rsplit('.',1)[0]: ROLE_IDS[role] for role,PathName in FILENAMES.items()}


def load_system_cursor(role):
    identity = ROLE_NAMES[role]
    function = _signature(USER32, 'LoadCursorW', [wintypes.HINSTANCE, ctypes.c_void_p], wintypes.HANDLE)
    cursor = function(None, ctypes.c_void_p(identity))
    if not cursor:
        raise ctypes.WinError(ctypes.get_last_error())
    return cursor


def set_system_cursor(cursor):
    _signature(USER32, 'SetCursor', [wintypes.HANDLE], wintypes.HANDLE)(cursor)


class NativeCursorFilter(QAbstractNativeEventFilter):
    def show_role(self, role):
        set_system_cursor(load_system_cursor(role))

    def nativeEventFilter(self, event_type, message):
        msg = wintypes.MSG.from_address(int(message))
        if msg.message != 0x20 or msg.lParam & 0xffff != 1:  # WM_SETCURSOR, client area
            return False, 0
        widget = QApplication.widgetAt(QCursor.pos())
        while widget is not None:
            role = widget.property('cursorRole')
            if role:
                self.show_role(role)
                return True, 1
            widget = widget.parentWidget()
        return False, 0
