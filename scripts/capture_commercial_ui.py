"""Pointer-only offscreen evidence; never connects to the Windows backend."""
import os
import argparse
import json
import math
from pathlib import Path
import sys
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))
from scripts.safe_preview import SafePreviewWindow, isolated_update_services


@isolated_update_services()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=('before', 'after'), default='after')
    parser.add_argument('--show', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if not args.show:
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
    from pointer.cursor.settings import CursorSettings
    app = QApplication.instance() or QApplication([])
    backend = Mock()
    backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
    backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
    for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
        getattr(backend, name).side_effect = RuntimeError('Isolated preview blocks system operations')
    window = SafePreviewWindow(backend)
    window.status_timer.stop()
    window._prewarm_timer.stop()
    window.show()
    if args.show:
        app.exec()
        return
    output = args.output or ROOT / '.local' / 'commercial-redesign' / args.phase
    output.mkdir(parents=True, exist_ok=True)
    measurements = {}
    for dark in (False, True):
        if window.ui_dark != dark:
            window.toggle_workspace_theme()
        theme = 'dark' if dark else 'light'
        for width, height in ((1180, 800), (880, 620)):
            window.resize(width, height)
            window.select_page(0)
            scroll = window.stack.widget(0)
            scroll.verticalScrollBar().setValue(0)
            app.processEvents()
            def point(widget):
                p = widget.mapTo(window, widget.rect().center())
                return [p.x(), p.y()]
            def distance(a, b):
                return round(math.dist(point(a), point(b)), 1)
            preset = window.pages[0].preset_buttons[1][0]
            visible = scroll.viewport().rect().contains(preset.mapTo(scroll.viewport(), preset.rect().center()))
            window.grab().save(str(output / f'appearance-{theme}-{width}.png'))
            scroll.ensureWidgetVisible(preset)
            app.processEvents()
            measurements[f'{theme}-{width}'] = {
                'device_pixel_ratio': window.devicePixelRatioF(),
                'horizontal_scroll_maximum': scroll.horizontalScrollBar().maximum(),
                'preset_columns': window.pages[0]._preset_columns,
                'apply_discard_center_distance_logical_px': distance(window.apply_button, window.discard),
                'preset_apply_center_distance_logical_px': distance(preset, window.apply_button),
                'preset_requires_initial_scroll': not visible,
                'choose_preset_then_apply_actions': 2 if visible else 3,
                'apply_visible': window.apply_button.isVisible(),
                'preset_center': point(preset), 'apply_center': point(window.apply_button),
            }
            window.grab().save(str(output / f'palette-{theme}-{width}.png'))
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
            app.processEvents()
            window.grab().save(str(output / f'palette-bottom-{theme}-{width}.png'))
            window.pages[0].open_advanced()
            app.processEvents()
            app.processEvents()
            window.grab().save(str(output / f'custom-{theme}-{width}.png'))
            window.pages[0].reset_color_session()
            for page, label in ((1, 'motion'), (2, 'tests'), (3, 'settings')):
                window.select_page(page)
                app.processEvents()
                window.grab().save(str(output / f'{label}-{theme}-{width}.png'))
    window.resize(1180, 800)
    window.select_page(0)
    window.change(size=64)
    if hasattr(window.preview, 'scale'):
        window.preview.scale.setCurrentIndex(window.preview.scale.findData('actual'))
    app.processEvents()
    window.grab().save(str(output / 'actual-size-64.png'))
    surface = window.preview.surfaces[0]
    surface.hovered = True
    window.grab().save(str(output / 'hover.png'))
    surface.pressed = True
    window.grab().save(str(output / 'pressed.png'))
    surface.release_preview_press()
    surface.hovered = False
    surface.setFocus(Qt.FocusReason.TabFocusReason)
    surface.setProperty('keyboardFocus', True)
    app.processEvents()
    window.grab().save(str(output / 'focus.png'))
    surface.clearFocus()
    window.preview.role.showPopup()
    app.processEvents()
    window.preview.role.view().scrollToBottom()
    app.processEvents()
    window.preview.role.view().grab().save(str(output / 'roles-popup.png'))
    window.preview.role.hidePopup()
    window.operation_failed('Isolated simulated error; draft retained')
    app.processEvents()
    window.grab().save(str(output / 'error.png'))
    window.busy = True
    window.stack.setEnabled(False)
    window.sync()
    app.processEvents()
    window.grab().save(str(output / 'loading.png'))
    window._replace_draft = True
    window._operation_message = '模拟应用结果 · 隔离预览'
    window.operation_done({'settings': window.draft().to_dict(), 'running': False})
    app.processEvents()
    window.grab().save(str(output / 'simulated-success.png'))
    (output / 'measurements.json').write_text(json.dumps(measurements, indent=2), encoding='utf-8')
    backend.apply.assert_not_called()
    window.busy = False
    window.stack.setEnabled(True)
    window.discard_changes()
    window.close()
    print(output)


if __name__ == '__main__':
    main()
