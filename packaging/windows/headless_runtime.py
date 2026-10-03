"""Keep the cursor helper free of Qt during PyInstaller initialization.

Custom runtime hooks run before the bundled hooks. The PySide hook normally
imports QtCore to register qt.conf; a --run process never needs that resource.
GUI and diagnosis launches retain the standard relocation behavior.
"""
import sys

if '--run' in sys.argv:
    from _pyi_rth_utils import qt
    qt.create_embedded_qt_conf = lambda *args, **kwargs: None
