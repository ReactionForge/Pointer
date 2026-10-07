"""Deterministic down/hold/release evidence through the guarded Qt preview."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import argparse
import json
import sys
from pathlib import Path
from unittest.mock import Mock, patch
ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'src')]
from PIL import Image
from PySide6.QtCore import Qt, QEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from pointer.cursor.settings import CursorSettings
from pointer.cursor.art.families import RECOMMENDED_STYLES
from scripts.safe_preview import SafePreviewWindow, isolated_update_services


@isolated_update_services()
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT/'.local/art-v3/motion-review')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    backend = Mock()
    backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
    backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
    for name in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
        getattr(backend, name).side_effect = RuntimeError('Mock motion review blocks system operations')
    window = SafePreviewWindow(backend)
    window.status_timer.stop()
    window._prewarm_timer.stop()
    window.preview.timer.stop()
    window.resize(1180, 800)
    window.show()
    report = {}
    for dark in (False, True):
        if window.ui_dark != dark:
            window.toggle_workspace_theme()
        theme = 'dark' if dark else 'light'
        for mode in ('tilt', 'shrink', 'spring', 'off', 'trail', 'pulse'):
            for role in ('arrow', 'hand'):
                for style in RECOMMENDED_STYLES:
                    window.preview.clear_press()
                    window.change(style=style, motion=mode, size=32, strength=50, press_ms=60, release_ms=150)
                    panel = window.preview
                    panel.role.setCurrentIndex(panel.role.findData(role))
                    panel.scale.setCurrentIndex(0)
                    panel.background.setCurrentIndex(panel.background.findData(theme))
                    surface = panel.surfaces[int(dark)]
                    surface.setFixedSize(280, 250)
                    app.processEvents()
                    frames, sequence = [], []
                    key = f'{style}-{role}-{mode}-{theme}'
                    def record(name, now):
                        with patch('pointer.ui.preview.time.monotonic', return_value=now):
                            panel.tick()
                        app.processEvents()
                        path = args.output/f'{key}-{name}.png'
                        surface.grab().save(str(path))
                        with Image.open(path) as image:
                            frames.append(image.convert('RGB').copy())
                        sequence.append({'phase': name, 'time_ms': round((now-1)*1000),
                                         'frame': panel.frame, 'down': panel.down})
                    record('rest', 1.0)
                    QTest.mousePress(surface, Qt.MouseButton.LeftButton, pos=surface.rect().center())
                    record('down', 1.0)
                    record('press-20', 1.02)
                    record('press-40', 1.04)
                    record('pressed', 1.06)
                    record('hold', 1.20)
                    QTest.mouseRelease(surface, Qt.MouseButton.LeftButton, pos=surface.rect().center())
                    record('release', 1.20)
                    record('release-40', 1.24)
                    record('release-80', 1.28)
                    record('release-120', 1.32)
                    record('restored', 1.36)
                    assert panel.frame == 0 and not panel.down, key
                    frames[0].save(args.output/f'{key}.gif', save_all=True, append_images=frames[1:],
                                   duration=[180, 80, 80, 80, 160, 300, 80, 100, 100, 100, 220], loop=0)
                    report[key] = sequence
                    QTest.mousePress(surface, Qt.MouseButton.LeftButton, pos=surface.rect().center())
                    with patch('pointer.ui.preview.time.monotonic', return_value=2.0): panel.tick()
                    QApplication.sendEvent(surface, QEvent(QEvent.Type.WindowDeactivate))
                    assert not panel.down and not surface.pressed
                    with patch('pointer.ui.preview.time.monotonic', return_value=2.0): panel.tick()
                    with patch('pointer.ui.preview.time.monotonic', return_value=2.2): panel.tick()
                    assert panel.frame == 0
                    surface.setMinimumSize(0, 180)
                    surface.setMaximumSize(16777215, 16777215)
    backend.apply.assert_not_called()
    window.discard_changes()
    window.close()
    (args.output/'timeline.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(f'{len(report)} guarded mouse-down/hold/release sequences; cancellation restored; no system operations.')


if __name__ == '__main__':
    main()
