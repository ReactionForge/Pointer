"""Approved graphite two-page candidate with Mock operations and updater isolation."""
import argparse
import os
import sys
import json
from pathlib import Path
from unittest.mock import Mock
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from scripts.safe_preview import SafePreviewWindow, isolated_update_services, ISOLATED_UPDATE_MESSAGE
from pointer.ui.approved_workspace import ApprovedWindow


class SafeApprovedWindow(ApprovedWindow):
    # Keep one Qt widget inheritance chain; reuse the exact guarded callbacks.
    _blocked_update = SafePreviewWindow._blocked_update
    check_updates_interactive = _blocked_update
    _check_update_silent_startup = _blocked_update
    _show_update_dialog = _blocked_update

    def __init__(self, backend):
        super().__init__(backend)
        self.pages[3].update_status_lbl.setText(ISOLATED_UPDATE_MESSAGE)


@isolated_update_services()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--show', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT/'.local/approved-ui/pages')
    args = parser.parse_args()
    if not args.show:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from pointer.cursor.settings import CursorSettings
    app = QApplication.instance() or QApplication([])
    backend = Mock()
    backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
    backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
    for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
        getattr(backend, name).side_effect = RuntimeError('Isolated reference preview blocks system actions')
    window = SafeApprovedWindow(backend)
    window.status_timer.stop()
    window._prewarm_timer.stop()
    window.show()
    if args.show:
        app.exec()
        return
    window.preview.timer.stop()
    args.output.mkdir(parents=True, exist_ok=True)
    measurements = {}
    for dark in (False, True):
        if window.ui_dark != dark: window.toggle_workspace_theme()
        theme = 'dark' if dark else 'light'
        for width, height in ((880, 620), (1100, 830), (1800, 900)):
            window.resize(width, height)
            for index, page in ((0, 'appearance'), (3, 'settings')):
                window.select_page(index)
                scroll = window.stack.widget(index)
                scroll.verticalScrollBar().setValue(0)
                app.processEvents()
                window.grab().save(str(args.output/f'{page}-{theme}-{width}.png'))
                measurements[f'{page}-{theme}-{width}'] = {'actual_size': [window.width(), window.height()],
                    'nav_width': window.nav_rail.width(), 'navigation': [[b.width(), b.height()] for b in window.navigation],
                    'horizontal_scroll': scroll.horizontalScrollBar().maximum(),
                    'editing_width': window.content_widget.width(), 'preview_width': window.preview.width()}
                if index == 0:
                    measurements[f'{page}-{theme}-{width}'].update(
                        shape_columns=window.shape_gallery.columns,
                        shape_bounds=[[b.x(), b.y(), b.width(), b.height()] for b in window.pages[0].shape_buttons.values()],
                        palettes_visible=[b.mapTo(scroll.viewport(), b.rect().bottomRight()).y() <= scroll.viewport().height()
                                          for b, _ in window.pages[0].preset_buttons])
                scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
                app.processEvents()
                window.grab().save(str(args.output/f'{page}-{theme}-{width}-bottom.png'))
                scroll.verticalScrollBar().setValue(0)
                window.change(size=48)
                app.processEvents()
                window.grab().save(str(args.output/f'{page}-{theme}-{width}-dirty.png'))
                window.discard_changes()
                window.toast.hide()
            window.select_page(0)
            window.preview.role.setFocus(Qt.FocusReason.TabFocusReason)
            window.preview.role.setProperty('keyboardFocus', True)
            app.processEvents()
            window.grab().save(str(args.output/f'focus-{theme}-{width}.png'))
            window.change(size=64)
            app.processEvents()
            window.grab().save(str(args.output/f'actual-64-{theme}-{width}.png'))
            window.discard_changes()
            window.toast.hide()
    backend.apply.assert_not_called()
    window.close()
    (args.output/'measurements.json').write_text(json.dumps(measurements, indent=2), encoding='utf8')
    print(args.output)


if __name__ == '__main__':
    main()
