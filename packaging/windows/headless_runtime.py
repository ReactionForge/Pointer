"""Keep the cursor helper free of Qt during PyInstaller initialization.

Custom runtime hooks run before the bundled hooks. The PySide hook normally
imports QtCore to register qt.conf; cursor and prewarm workers do not need it.
GUI and diagnosis launches retain the standard relocation behavior.
"""
import sys

if any(action in sys.argv for action in ('--run', '--prepare-cursors')):
    from _pyi_rth_utils import qt
    qt.create_embedded_qt_conf = lambda *args, **kwargs: None
