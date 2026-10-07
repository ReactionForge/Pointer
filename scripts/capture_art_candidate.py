"""New art-direction review, independent of frozen commercial evidence."""
import os
import argparse
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import json
import sys
from pathlib import Path
from unittest.mock import Mock
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from pointer.cursor.settings import CursorSettings
from pointer.cursor.art.families import RECOMMENDED_STYLES
from pointer.ui.pages.appearance import WORKSPACE_PRESETS
from scripts.safe_preview import SafePreviewWindow, isolated_update_services


@isolated_update_services()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'.local/art-direction-v2/final')
    args = parser.parse_args()
    app = QApplication.instance() or QApplication([])
    backend = Mock()
    backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
    backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
    for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
        getattr(backend, name).side_effect = RuntimeError('Isolated art review blocks system operations')
    window = SafePreviewWindow(backend)
    window.status_timer.stop()
    window._prewarm_timer.stop()
    window.preview.timer.stop()
    window.show()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    evidence = {}
    for dark in (False, True):
        if window.ui_dark != dark:
            window.toggle_workspace_theme()
        theme = 'dark' if dark else 'light'
        window.toast.hide()
        window.feedback.setText('预览不改变系统光标')
        window.preview.clear_press()
        for width, height in ((880, 620), (1180, 800), (1536, 900)):
            window.resize(width, height)
            window.select_page(0)
            scroll = window.stack.widget(0)
            scroll.verticalScrollBar().setValue(0)
            app.processEvents()
            app.processEvents()
            window.grab().save(str(output/f'shell-{theme}-{width}.png'))
            evidence[f'{theme}-{width}'] = {
                'actual_window_size': [window.width(), window.height()],
                'navigation_target_sizes': [[b.width(), b.height()] for b in window.navigation],
                'inspector_horizontal_scroll_max': scroll.horizontalScrollBar().maximum(),
                'nav_rail_width': window.nav_rail.width(),
            }
            scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum())
            app.processEvents()
            window.grab().save(str(output/f'palette-bottom-{theme}-{width}.png'))
            window.pages[0].open_advanced()
            app.processEvents()
            app.processEvents()
            window.grab().save(str(output/f'custom-{theme}-{width}.png'))
            window.pages[0].reset_color_session()
        window.resize(1180, 800)
        window.select_page(0)
        for style in RECOMMENDED_STYLES:
            window.change(style=style)
            for size in (24, 32, 48, 64):
                window.change(size=size)
                window.preview.scale.setCurrentIndex(1)
                app.processEvents()
                window.grab().save(str(output/f'{style}-{size}-{theme}-actual.png'))
            window.preview.scale.setCurrentIndex(0)
            app.processEvents()
            window.grab().save(str(output/f'{style}-{theme}-enlarged.png'))
        window.change(style='quill', size=32)
        for preset in WORKSPACE_PRESETS:
            window.pages[0].apply_preset(preset)
            app.processEvents()
            window.grab().save(str(output/f'palette-{preset["id"]}-{theme}.png'))
        window.select_page(1)
        window.pages[1].motion_recipes[0][0].click()
        app.processEvents()
        window.grab().save(str(output/f'motion-tap-{theme}.png'))
        window.change(motion='trail')
        app.processEvents()
        window.grab().save(str(output/f'motion-trail-retired-{theme}.png'))
        window.change(motion='shrink')
        window.select_page(0)
        for name, widget in [('navigation', window.navigation[0]),
                             ('shape', window.pages[0].shape_buttons['quill']),
                             ('palette', window.pages[0].preset_buttons[0][0]),
                             ('apply', window.apply_button),
                             ('surface', window.preview.surfaces[0])]:
            scroll.ensureWidgetVisible(widget) if name in ('shape', 'palette') else None
            app.processEvents()
            widget.setFocus(Qt.FocusReason.TabFocusReason)
            widget.setProperty('keyboardFocus', True)
            widget.update()
            app.processEvents()
            window.grab().save(str(output/f'{name}-focus-{theme}.png'))
            QTest.mouseMove(widget, widget.rect().center())
            app.processEvents()
            window.grab().save(str(output/f'{name}-hover-{theme}.png'))
            QTest.mousePress(widget, Qt.MouseButton.LeftButton, pos=widget.rect().center())
            app.processEvents()
            window.grab().save(str(output/f'{name}-pressed-{theme}.png'))
            # Release outside: do not activate Apply while recording its feedback.
            QTest.mouseRelease(widget, Qt.MouseButton.LeftButton, pos=widget.rect().bottomRight()+widget.rect().bottomRight())
            app.processEvents()
        window.discard_changes()
    backend.apply.assert_not_called()
    window.discard_changes()
    window.close()
    (output/'layout.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
