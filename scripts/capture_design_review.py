"""Local-only, isolated Qt evidence for the six selected Pointer regions."""
import os
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
sys.path.insert(0, str(ROOT))
from scripts.safe_preview import SafePreviewWindow, isolated_update_services
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QLabel
from PySide6.QtTest import QTest
from pointer.cursor.settings import CursorSettings
from pointer.ui.colors import theme_colors


def contrast(a, b):
    def luminance(color):
        values = [color.redF(), color.greenF(), color.blueF()]
        return sum((v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4) * w
                   for v, w in zip(values, (.2126, .7152, .0722)))
    low, high = sorted((luminance(a), luminance(b)))
    return round((high + .05) / (low + .05), 2)


@isolated_update_services()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=('before', 'after'), required=True)
    parser.add_argument('--palette-only', action='store_true')
    parser.add_argument('--p2-only', action='store_true')
    args = parser.parse_args()
    output = ROOT / '.local' / 'design-review' / args.phase
    output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    backend = Mock()
    backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
    backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
    for operation in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
        getattr(backend, operation).side_effect = RuntimeError('隔离审阅不执行系统操作')
    window = SafePreviewWindow(backend)
    window.status_timer.stop()
    window._prewarm_timer.stop()
    window.show()
    if args.p2_only:
        evidence = {}
        window.resize(880, 620)
        for dark in (False, True):
            if window.ui_dark != dark:
                window.toggle_workspace_theme()
            theme = 'dark' if dark else 'light'
            window.select_page(3)
            switch = window.pages[3].startup
            switch.setEnabled(False)
            app.processEvents()
            switch.grab().save(str(output / f'disabled-switch-{theme}.png'))
            window.grab().save(str(output / f'disabled-switch-context-{theme}-880.png'))
            switch_image = switch.grab().toImage()
            evidence[theme] = {'disabled_switch_top_border': switch_image.pixelColor(20, 0).name(),
                               'disabled_switch_track': switch_image.pixelColor(20, 5).name()}
            switch.setEnabled(True)
            window.select_page(0)
            app.processEvents()
            QApplication.setActiveWindow(window)
            surface = window.preview.hero
            surface.clearFocus()
            surface.setFocus(Qt.FocusReason.TabFocusReason)
            app.processEvents()
            evidence[theme]['keyboard_focus_visible'] = surface.hasFocus() and bool(surface.property('keyboardFocus'))
            window.grab().save(str(output / f'preview-keyboard-focus-{theme}-880.png'))
            QTest.keyPress(surface, Qt.Key.Key_Space)
            QTest.qWait(60)
            app.processEvents()
            evidence[theme]['space_pressed'] = window.preview.down
            window.grab().save(str(output / f'preview-keyboard-press-{theme}-880.png'))
            QTest.keyRelease(surface, Qt.Key.Key_Space)
            evidence[theme]['space_released'] = not window.preview.down
            combo = window.preview.role
            combo.showPopup()
            app.processEvents()
            combo.view().window().grab().save(str(output / f'role-menu-first-{theme}-880.png'))
            last = combo.model().index(combo.count() - 1, 0)
            combo.view().scrollTo(last)
            app.processEvents()
            evidence[theme]['role_count'] = combo.count()
            evidence[theme]['last_role'] = combo.itemData(combo.count() - 1)
            evidence[theme]['last_role_visible'] = combo.view().viewport().rect().contains(combo.view().visualRect(last).center())
            evidence[theme]['horizontal_scroll_max'] = combo.view().horizontalScrollBar().maximum()
            combo.view().window().grab().save(str(output / f'role-menu-last-{theme}-880.png'))
            combo.hidePopup()
        (output / 'p2-evidence.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        window.close()
        print(output / 'p2-evidence.json')
        return
    if args.palette_only:
        page = window.pages[0]
        page.open_advanced()
        for dark in (False, True):
            if window.ui_dark != dark:
                window.toggle_workspace_theme()
            for width, height in ((1180, 800), (880, 620)):
                window.resize(width, height)
                app.processEvents()
                page.reveal_colors()
                app.processEvents()
                window.grab().save(str(output / f'palette-{"dark" if dark else "light"}-{width}.png'))
        window.grab().save(str(output / 'palette.png'))
        window.close()
        print(output / 'palette.png')
        return
    measurements = {}
    for dark in (False, True):
        if window.ui_dark != dark:
            window.toggle_workspace_theme()
        theme = 'dark' if dark else 'light'
        colors = theme_colors(dark)
        window.select_page(3)
        app.processEvents()
        measurements[theme] = {}
        for name in ('rowTitle', 'rowSubtitle', 'sectionTitle'):
            labels = window.pages[3].findChildren(QLabel, name)
            measurements[theme][name] = min(contrast(label.palette().color(QPalette.ColorRole.WindowText), QColor(colors['surface'])) for label in labels)
        switch = window.pages[3].startup
        measurements[theme]['off_switch_track'] = contrast(switch.grab().toImage().pixelColor(20, 5), QColor(colors['surface']))
        measurements[theme]['selected_navigation'] = contrast(QColor(colors['selected_text']), QColor(colors['selected']))
        measurements[theme]['keyboard_focus_boundary'] = contrast(QColor(colors['focus']), QColor(colors['surface']))
        drag = window.pages[2].scenario('drag')
        measurements[theme]['drag_label'] = contrast(drag.label.palette().color(QPalette.ColorRole.WindowText), QColor(colors['raised']))
        for width, height in ((1180, 800), (880, 620)):
            window.resize(width, height)
            for page, name in ((0, 'family'), (2, 'tests'), (3, 'settings')):
                window.select_page(page)
                window.stack.widget(page).verticalScrollBar().setValue(0)
                app.processEvents()
                window.grab().save(str(output / f'{name}-{theme}-{width}.png'))
                if page == 2:
                    window.stack.widget(page).ensureWidgetVisible(window.pages[2].scenario('drag'))
                    app.processEvents()
                    window.grab().save(str(output / f'drag-{theme}-{width}.png'))
    (output / 'contrast.json').write_text(json.dumps({'scope': 'Targeted text palettes and actual painted off-switch track; navigation/focus token pairs. No whole-app accessibility claim.', 'ratios': measurements}, indent=2), encoding='utf-8')
    window.resize(1180, 800)
    window.select_page(0)
    if window.ui_dark:
        window.toggle_workspace_theme()
    window.change(size=40)
    window.theme_button.setFocus(Qt.FocusReason.TabFocusReason)
    app.processEvents()
    window.grab().save(str(output / 'dirty-keyboard-focus.png'))
    window.theme_button.clearFocus()
    QTest.mouseMove(window.theme_button, window.theme_button.rect().center())
    app.processEvents()
    window.grab().save(str(output / 'mouse-hover.png'))
    window.subtitle.setText('较长的中文说明：配色仅更新草稿，请检查浅色与深色背景中的主体、描边和光晕，然后使用顶部应用更改提交。')
    window.resize(880, 620)
    app.processEvents()
    window.grab().save(str(output / 'long-chinese-880.png'))
    window.operation_failed('隔离夹具：模拟错误，草稿保留')
    app.processEvents()
    window.grab().save(str(output / 'error.png'))
    window.busy = True
    window.sync()
    app.processEvents()
    window.grab().save(str(output / 'disabled.png'))
    window.busy = False
    window.discard_changes()
    window.close()
    print(output)


if __name__ == '__main__':
    main()
