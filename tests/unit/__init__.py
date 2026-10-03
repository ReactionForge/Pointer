"""Unit tests may load cursors, but must never mutate the user's Windows setup."""
import winreg
from pointer.windows import engine, scheme


def _deny_system_mutation(*args, **kwargs):
    raise RuntimeError('Unit test attempted a real system change; mock the Windows boundary')


winreg.SetValueEx = _deny_system_mutation
winreg.DeleteValue = _deny_system_mutation
scheme.USER32.SetSystemCursor = _deny_system_mutation
scheme.USER32.SystemParametersInfoW = _deny_system_mutation
engine.USER32.SetSystemCursor = _deny_system_mutation
