"""Own Qt boxes under simulated application palettes; never switch Windows theme."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import sys
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from pointer.ui.theme import initialize_fonts, STYLE
from pointer.ui.family_workspace import workspace_style
from pointer.ui.confirmations import confirmation_box


def main():
    app = QApplication.instance() or QApplication([])
    initialize_fonts()
    original = app.palette()
    output = ROOT/'.local/reference-ui/dialogs'
    output.mkdir(parents=True, exist_ok=True)
    report = {}
    for system_dark in (False, True):
        palette = QPalette(original)
        palette.setColor(QPalette.ColorRole.Window, QColor('#202020' if system_dark else '#ffffff'))
        palette.setColor(QPalette.ColorRole.WindowText, QColor('#ffffff' if system_dark else '#202126'))
        app.setPalette(palette)
        for pointer_dark in (False, True):
            owner = QWidget()
            owner.ui_dark = pointer_dark
            owner.setStyleSheet(STYLE + workspace_style(pointer_dark))
            for kind, title, message, proceed, keep in (
                ('close', '未应用的修改', '放弃未应用的修改并关闭窗口？', '放弃修改', '继续编辑'),
                ('reset', '重置配置', '现有配置无法读取。保留原文件副本并使用默认配置？', '使用默认配置', '取消'),
                ('restore', '恢复原光标', '恢复 Windows 原光标并关闭 Pointer 开机启动？', '恢复原光标', '取消')):
                box = confirmation_box(owner, title, message, proceed, keep)
                box.show()
                app.processEvents()
                key = f'{kind}-system-{int(system_dark)}-pointer-{int(pointer_dark)}'
                report[key] = {'background': box.palette().color(QPalette.ColorRole.Window).name(),
                               'text': box.palette().color(QPalette.ColorRole.WindowText).name(),
                               'default': box.defaultButton().text(), 'escape': box.escapeButton().text()}
                box.grab().save(str(output/f'{key}.png'))
                button = box.button(QMessageBox.StandardButton.Yes)
                button.setFocus(Qt.FocusReason.TabFocusReason)
                app.processEvents()
                box.grab().save(str(output/f'{key}-focus.png'))
                QTest.mouseMove(button, button.rect().center())
                app.processEvents()
                box.grab().save(str(output/f'{key}-hover.png'))
                button.setDown(True)
                app.processEvents()
                box.grab().save(str(output/f'{key}-pressed.png'))
                button.setDown(False)
                button.setEnabled(False)
                app.processEvents()
                box.grab().save(str(output/f'{key}-disabled.png'))
                box.close()
            owner.close()
    app.setPalette(original)
    (output/'matrix.json').write_text(json.dumps({'scope':'Qt application palettes simulated; Windows and other software untouched', 'cases':report}, indent=2), encoding='utf8')
    print(output)


if __name__ == '__main__':
    main()
