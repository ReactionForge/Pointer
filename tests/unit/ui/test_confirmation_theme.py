"""Owned confirmation safety and theme isolation without changing Windows."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock, patch
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPalette, QColor, QCloseEvent
from PySide6.QtWidgets import QApplication, QWidget, QMessageBox, QFileDialog
from PySide6.QtTest import QTest
from pointer.ui.theme import initialize_fonts
from pointer.ui.colors import theme_colors
from pointer.ui.confirmations import confirmation_box, ask_confirmation
from pointer.ui.main_window import MainWindow
from pointer.cursor.settings import CursorSettings

APP = QApplication.instance() or QApplication([])
initialize_fonts()


class ConfirmationThemeTests(unittest.TestCase):
    def test_system_and_pointer_theme_cross_product_uses_explicit_readable_owned_palette(self):
        original = APP.palette()
        try:
            for system_dark in (False, True):
                palette = QPalette(original)
                palette.setColor(QPalette.ColorRole.Window, QColor('#202020' if system_dark else '#ffffff'))
                APP.setPalette(palette)
                for pointer_dark in (False, True):
                    owner = QWidget()
                    owner.ui_dark = pointer_dark
                    box = confirmation_box(owner, '未应用的修改', '放弃未应用的修改并关闭窗口？', '放弃修改', '继续编辑')
                    expected = theme_colors(pointer_dark)
                    self.assertEqual(box.palette().color(QPalette.ColorRole.Window).name(), expected['canvas'])
                    self.assertEqual(box.palette().color(QPalette.ColorRole.WindowText).name(), expected['text'])
                    self.assertIs(box.defaultButton(), box.button(QMessageBox.StandardButton.No))
                    self.assertIs(box.escapeButton(), box.button(QMessageBox.StandardButton.No))
                    box.deleteLater()
                    owner.deleteLater()
            selector = QFileDialog()
            self.assertEqual(selector.styleSheet(), '')
        finally:
            APP.setPalette(original)

    def test_escape_close_and_enter_choose_keep_while_explicit_proceed_returns_yes(self):
        owner = QWidget()
        owner.ui_dark = False
        for action in ('escape', 'close', 'enter', 'proceed'):
            box = confirmation_box(owner, '未应用的修改', '放弃未应用的修改并关闭窗口？', '放弃修改', '继续编辑')
            def respond():
                if action == 'close': box.close()
                elif action == 'proceed': box.button(QMessageBox.StandardButton.Yes).click()
                else: QTest.keyClick(box, Qt.Key.Key_Escape if action == 'escape' else Qt.Key.Key_Return)
            QTimer.singleShot(0, respond)
            result = box.exec()
            self.assertEqual(result, QMessageBox.StandardButton.Yes if action == 'proceed' else QMessageBox.StandardButton.No)
        owner.deleteLater()

    def test_owned_close_reset_and_restore_keep_draft_and_never_act_on_cancel(self):
        backend = Mock()
        backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        window = MainWindow(backend)
        window.change(size=48)
        draft = window.draft()
        with patch('pointer.ui.main_window.ask_confirmation', return_value=QMessageBox.StandardButton.No), \
                patch.object(window, 'run_operation') as operation:
            event = QCloseEvent()
            window.closeEvent(event)
            self.assertFalse(event.isAccepted())
            self.assertEqual(window.draft(), draft)
            window.load_error = 'simulated unreadable configuration'
            window.reset_defaults()
            self.assertEqual(window.draft(), draft)
            window.confirm_restore()
            operation.assert_not_called()
            backend.restore.assert_not_called()
        window.load_error = None
        window.discard_changes()
        window.close()
