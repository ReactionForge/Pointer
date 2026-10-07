"""Persistent window-only appearance review with cursor/update operations blocked."""
import argparse
import sys
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from scripts.capture_material_ui import SafeMaterialWindow
from scripts.safe_preview import isolated_update_services
from pointer.cursor.settings import CursorSettings
from pointer.ui.sidebar_settings import SidebarStore


@isolated_update_services()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--page', type=int, choices=(0, 1, 2, 3), default=0)
    parser.add_argument('--light', action='store_true')
    parser.add_argument('--width', type=int, default=1360)
    parser.add_argument('--height', type=int, default=920)
    parser.add_argument('--settings', type=Path, default=ROOT / '.local/material-v3/sidebar.json')
    args = parser.parse_args()
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    helper, composition_error = None, None
    if sys.platform == 'win32' and app.platformName() == 'windows':
        from pointer.windows.composition_host import prepare_helper
        try:
            helper = prepare_helper(ROOT / '.local/material-v4/composition-cache')
        except OSError as error:
            composition_error = str(error)
    backend = Mock()
    backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
    backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
    backend.runtime_status.return_value = {'running': False}
    for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
        getattr(backend, name).side_effect = RuntimeError('隔离预览：系统光标及启动操作已阻止。')
    window = SafeMaterialWindow(backend, sidebar_store=SidebarStore(args.settings),
                               composition_helper=helper, composition_error=composition_error)
    window.setWindowTitle('Pointer')
    if window._backdrop_host is not None:
        window._backdrop_host.failed.connect(
            lambda reason: print('Composition unavailable: ' + reason, file=sys.stderr, flush=True))
    elif composition_error:
        print('Composition unavailable: ' + composition_error, file=sys.stderr, flush=True)
    window.status_timer.stop()
    window._prewarm_timer.stop()
    window.resize(args.width, args.height)
    window.select_page(args.page)
    if args.light and window.ui_dark:
        window.toggle_workspace_theme()
    window.show()
    app.exec()
    for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
        getattr(backend, name).assert_not_called()


if __name__ == '__main__':
    main()
