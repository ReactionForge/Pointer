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
from pointer.ui.material_workspace import MaterialWindow
from pointer.ui.sidebar_settings import SidebarStore


class SafeMaterialWindow(MaterialWindow):
    # Keep one Qt widget inheritance chain; reuse the exact guarded callbacks.
    _blocked_update = SafePreviewWindow._blocked_update
    check_updates_interactive = _blocked_update
    _check_update_silent_startup = _blocked_update
    _show_update_dialog = _blocked_update

    def __init__(self, backend, policy=None, sidebar_store=None, **material_options):
        super().__init__(backend, policy=policy, sidebar_store=sidebar_store, **material_options)
        self.pages[3].update_status_lbl.setText(ISOLATED_UPDATE_MESSAGE)
        self.setWindowTitle('Pointer · 双区材质 · 隔离预览')


@isolated_update_services()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--show', action='store_true')
    parser.add_argument('--output', type=Path, default=ROOT/'.local/material-v2/pages')
    args = parser.parse_args()
    if not args.show:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt, QPoint
    from PySide6.QtGui import QColor, QImage
    from pointer.cursor.settings import CursorSettings
    app = QApplication.instance() or QApplication([])
    helper, composition_error = None, None
    if args.show and sys.platform == 'win32' and app.platformName() == 'windows':
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
        getattr(backend, name).side_effect = RuntimeError('Isolated reference preview blocks system actions')
    window = SafeMaterialWindow(backend, sidebar_store=SidebarStore(ROOT/'.local/material-v3/sidebar.json') if args.show else None,
                               composition_helper=helper, composition_error=composition_error)
    window.status_timer.stop()
    window._prewarm_timer.stop()
    window.show()
    if args.show:
        app.exec()
        return
    window.preview.timer.stop()
    args.output.mkdir(parents=True, exist_ok=True)
    measurements = {}
    composition_checks = {}
    def capture(path):
        if window.preview.isVisible():
            for surface in window.preview.surfaces:
                surface.grab()
        snapshot = QImage(window.size(),QImage.Format.Format_ARGB32_Premultiplied)
        snapshot.fill(Qt.GlobalColor.transparent)
        window.render(snapshot)
        if window.preview.isVisible():
            image = snapshot
            counts = []
            for surface in window.preview.surfaces:
                origin = surface.mapTo(window, QPoint())
                bounds = surface.cursor_bounds.toRect().translated(origin).adjusted(20,20,-20,-20)
                background = QColor('#eef0f5' if surface.theme == 'light' else '#202329')
                pixels = sum(image.pixelColor(x, y) != background
                    for y in range(bounds.top(), bounds.bottom()+1)
                    for x in range(bounds.left(), bounds.right()+1))
                assert pixels > 20, f'Empty cursor layer: {path.name}/{surface.theme}'
                counts.append(pixels)
            composition_checks[path.name] = counts
        snapshot.save(str(path))
    for dark in (False, True):
        if window.ui_dark != dark: window.toggle_workspace_theme()
        theme = 'dark' if dark else 'light'
        for width, height in ((880, 620), (1180, 880), (1360, 920)):
            window.resize(width, height)
            for index, page in ((0, 'appearance'), (3, 'settings')):
                window.select_page(index)
                scroll = window.stack.widget(index)
                scroll.verticalScrollBar().setValue(0)
                app.processEvents()
                app.processEvents()  # settle QScrollArea's queued responsive relayout
                if index == 0:
                    # The production preview's timer normally schedules this
                    # paint; captures stop that timer to freeze the evidence.
                    window.preview.refresh()
                    for surface in window.preview.surfaces:
                        surface.grab()  # render the offscreen child before the parent snapshot
                    app.processEvents()
                capture(args.output/f'{page}-{theme}-{width}.png')
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
                capture(args.output/f'{page}-{theme}-{width}-bottom.png')
                scroll.verticalScrollBar().setValue(0)
                window.change(size=48)
                app.processEvents()
                capture(args.output/f'{page}-{theme}-{width}-dirty.png')
                window.discard_changes()
                window.toast.hide()
            window.select_page(0)
            window.preview.role.setFocus(Qt.FocusReason.TabFocusReason)
            window.preview.role.setProperty('keyboardFocus', True)
            app.processEvents()
            capture(args.output/f'focus-{theme}-{width}.png')
            window.change(size=64)
            app.processEvents()
            capture(args.output/f'actual-64-{theme}-{width}.png')
            window.discard_changes()
            window.toast.hide()
    backend.apply.assert_not_called()
    window.close()
    (args.output/'measurements.json').write_text(json.dumps(measurements, indent=2), encoding='utf8')
    (args.output/'composition-checks.json').write_text(json.dumps(composition_checks, indent=2), encoding='utf8')
    print(args.output)


if __name__ == '__main__':
    main()
