"""Capture only the Qt window using an isolated backend; never apply Windows settings."""
import argparse
import os
from pathlib import Path
import sys
from unittest.mock import Mock

if '--show' not in sys.argv:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))
from scripts.safe_preview import SafePreviewWindow, isolated_update_services
from PySide6.QtWidgets import QApplication
from pointer.cursor.settings import CursorSettings


@isolated_update_services()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT / '.local' / 'family-ui')
    parser.add_argument('--show', action='store_true', help='Open an isolated interactive review window')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    backend = Mock()
    backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
    backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
    for operation in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
        getattr(backend, operation).side_effect = RuntimeError('隔离审阅窗口不执行系统操作')
    window = SafePreviewWindow(backend)
    window.status_timer.stop()
    window._prewarm_timer.stop()
    window.show()
    if args.show:
        app.exec()
        return
    for theme in ('light', 'dark'):
        if (theme == 'dark') != window.ui_dark:
            window.toggle_workspace_theme()
        for width, height in ((1180, 800), (880, 620)):
            window.resize(width, height)
            app.processEvents()
            target = args.output / f'family-{theme}-{width}x{height}.png'
            window.grab().save(str(target))
            print(target)
            if width == 880:
                scroll = window.stack.widget(0)
                scroll.ensureWidgetVisible(window.pages[0].family_size)
                app.processEvents()
                window.grab().save(str(args.output / f'family-{theme}-880x620-controls.png'))
    window.resize(1180, 800)
    if window.ui_dark:
        window.toggle_workspace_theme()
    window.preview.role.setCurrentIndex(window.preview.role.findData('hand'))
    window.change(size=40)
    app.processEvents()
    window.grab().save(str(args.output / 'family-hand-draft.png'))
    window.discard_changes()
    window.close()


if __name__ == '__main__':
    main()
