"""Operation recovery, keyboard scopes and truthful feedback using isolated state."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import Mock, patch

from PySide6.QtCore import QCoreApplication, QEvent, QPoint, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QFrame

from pointer.cursor.settings import CursorSettings, SettingsStore
from pointer.ui.operation_feedback import FeedbackLabel
from pointer.ui.sidebar_settings import SidebarStore
from scripts.capture_material_ui import SafeMaterialWindow
from scripts.safe_preview import isolated_update_services

APP = QApplication.instance() or QApplication([])


class OperationFeedbackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pointer-ui-feedback-')
        self.config = SettingsStore(Path(self.temp.name))
        self.settings = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.config.save(self.settings)
        self.backend = Mock()
        self.backend.store = self.config
        self.backend.settings.return_value = self.config.load()
        self.backend.runtime_status.return_value = {'running': True}
        self.backend.apply.side_effect = lambda settings: {'settings': settings.to_dict()}
        for name in ('pause', 'resume', 'restore', 'set_startup'):
            getattr(self.backend, name).side_effect = AssertionError('No system operation in UI tests')
        self.isolation = isolated_update_services()
        self.isolation.__enter__()
        self.prewarm = patch('pointer.ui.main_window.MainWindow._schedule_prewarm')
        self.prewarm.start()
        self.window = SafeMaterialWindow(self.backend, sidebar_store=SidebarStore(Path(self.temp.name) / 'sidebar.json'))
        self.window.status_timer.stop()
        self.window._prewarm_timer.stop()
        self.window.preview.timer.stop()
        self.window.resize(880, 620)
        self.window.show()
        self.window.activateWindow()
        APP.processEvents()
        APP.processEvents()

    def tearDown(self):
        if self.window._feedback_dialog is not None:
            self.window._feedback_dialog.reject()
        self.settle_operations()
        self.window.discard_changes()
        self.window.close()
        self.window.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        APP.processEvents()
        self.prewarm.stop()
        self.isolation.__exit__(None, None, None)
        self.temp.cleanup()

    def settle_operations(self):
        deadline = time.monotonic() + 4
        while self.window._threads and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(self.window._threads, 'Mock operation thread did not finish')
        APP.processEvents()

    def test_long_plaintext_error_has_fixed_footer_full_copy_and_explicit_retry(self):
        w = self.window
        text = '外观已保存；光标应用失败：' + '中文路径无法访问 / <配置> & 原因。' * 25 + '\n保留草稿并重试。' * 12
        retry = Mock()
        w._set_operation_feedback(text, error=True, retry=retry, retry_text='重试应用')
        APP.processEvents()
        for width, height in ((880, 620), (1180, 800)):
            w.resize(width, height)
            APP.processEvents()
            self.assertIsInstance(w.feedback, FeedbackLabel)
            self.assertEqual(w.feedback.text(), text)
            self.assertEqual(w.feedback.toolTip(), text)
            self.assertTrue(w.feedback.is_elided())
            self.assertTrue(w.feedback_details.isVisible())
            self.assertEqual(w.findChild(QFrame, 'controlBar').height(), 64)
            self.assertLess(w.feedback.mapTo(w, QPoint()).x() + w.feedback.width(),
                            w.feedback_details.mapTo(w, QPoint()).x())
        original_clipboard = APP.clipboard().text()
        try:
            w.feedback_details.click()
            APP.processEvents()
            dialog = w._feedback_dialog
            self.assertEqual(dialog.body.toPlainText(), text)
            self.assertTrue(dialog.body.isReadOnly())
            dialog.copy_button.click()
            self.assertEqual(APP.clipboard().text(), text)
            self.assertEqual(dialog.copy_button.text(), '已复制全文')
            with patch.object(w, 'apply_draft') as apply:
                QTest.keyClick(dialog.body, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
                apply.assert_not_called()
            dialog.retry_button.click()
            retry.assert_called_once()
        finally:
            APP.clipboard().setText(original_clipboard)

    def test_combined_save_failure_keeps_cursor_draft_and_retries_only_pending_apply(self):
        w = self.window
        w.set_sidebar_transparency(100)
        w.change(size=48)
        desired = w.draft()
        self.backend.apply.side_effect = [OSError('mock cursor failure'), {'settings': desired.to_dict()}]
        with patch.object(w.sidebar_store, 'save', wraps=w.sidebar_store.save) as save:
            w.apply_draft()
            self.settle_operations()
            self.assertFalse(w.sidebar_dirty)
            self.assertEqual(w.draft(), desired)
            self.assertNotEqual(w.applied, desired)
            self.assertIn('外观已保存；光标应用失败', w.feedback.text())
            self.assertTrue(w.feedback.property('error'))
            self.assertEqual(w.apply_button.text(), '重试应用')
            self.backend.runtime_status.return_value = {'last_error': 'older runtime error'}
            w.refresh_status()
            self.assertIn('外观已保存；光标应用失败', w.feedback.text())
            self.backend.runtime_status.return_value = {'running': True}
            w.show_feedback_details()
            APP.processEvents()
            self.assertEqual(w._feedback_dialog.retry_button.text(), w.apply_button.text())
            w._feedback_dialog.retry_button.click()
            self.settle_operations()
            self.assertEqual(w.applied, desired)
            self.assertEqual(w.draft(), desired)
            self.assertFalse(w.feedback.property('error'))
            save.assert_called_once()
            self.assertEqual(self.backend.apply.call_count, 2)

    def test_save_failure_does_not_apply_cursor_and_retry_uses_latest_draft(self):
        w = self.window
        w.set_sidebar_transparency(100)
        w.change(size=48)
        with patch.object(w.sidebar_store, 'save', side_effect=OSError('isolated read-only config')):
            w.apply_draft()
        self.assertTrue(w.sidebar_dirty)
        self.assertIn('草稿均已保留', w.feedback.text())
        self.backend.apply.assert_not_called()
        w.change(size=64)
        w.show_feedback_details()
        APP.processEvents()
        w._feedback_dialog.retry_button.click()
        self.settle_operations()
        self.assertFalse(w.sidebar_dirty)
        self.assertEqual(self.backend.apply.call_args.args[0].size, 64)
        self.assertIn('外观已保存；光标配置已应用', w.feedback.text())

    def test_busy_guard_prevents_shortcuts_and_duplicate_apply(self):
        w = self.window
        gate = threading.Event()
        w.change(size=48)
        self.backend.apply.side_effect = lambda settings: (gate.wait(3), {'settings': settings.to_dict()})[1]
        try:
            w.apply_draft()
            APP.processEvents()
            self.assertTrue(w.busy)
            self.assertTrue(w.feedback_progress.isVisible())
            self.assertIn('正在处理', w.pages[2].context_status.text())
            w._activate_primary_shortcut()
            w._activate_page_shortcut(2)
            w.apply_draft()
            self.assertEqual(w.stack.currentIndex(), 0)
            self.assertFalse(w.apply_button.isEnabled())
        finally:
            gate.set()
            self.settle_operations()
        self.backend.apply.assert_called_once()
        self.assertFalse(w.feedback_progress.isVisible())

    def test_window_shortcuts_commit_numeric_input_and_do_not_repeat(self):
        w = self.window
        QTest.keyClick(w, Qt.Key.Key_4, Qt.KeyboardModifier.ControlModifier)
        self.assertEqual(w.stack.currentIndex(), 3)
        editor = w.sidebar_controls.transparency_value
        w.stack.widget(3).ensureWidgetVisible(editor)
        editor.setFocus()
        editor.lineEdit().selectAll()
        QTest.keyClicks(editor.lineEdit(), '60')
        self.assertFalse(w.sidebar_dirty, 'Typing alone should still be uncommitted')
        QTest.keyClick(editor, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
        APP.processEvents()
        self.assertFalse(w.sidebar_dirty)
        self.assertEqual(w.sidebar_saved.dark_alpha, 102)
        self.backend.apply.assert_not_called()
        with patch.object(w, 'apply_draft') as apply:
            QTest.keyClick(w, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
            apply.assert_not_called()
        with patch.object(w, 'select_page', wraps=w.select_page) as select:
            QTest.keyPress(w, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)
            for _ in range(3):
                QCoreApplication.sendEvent(w, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_3,
                    Qt.KeyboardModifier.ControlModifier, '3', True, 1))
            QTest.keyRelease(w, Qt.Key.Key_3, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(select.call_count, 1)
        self.assertEqual(w.stack.currentIndex(), 2)
        self.assertTrue(all(not shortcut.autoRepeat() for shortcut in w.page_shortcuts + w.primary_shortcuts))
        w.change(size=48)
        with patch.object(w, 'apply_draft') as apply:
            QTest.keyPress(w, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
            for _ in range(3):
                QCoreApplication.sendEvent(w, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Return,
                    Qt.KeyboardModifier.ControlModifier, '\r', True, 1))
            QTest.keyRelease(w, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
            apply.assert_called_once()

    def test_backdrop_sender_names_sidebar_and_full_window_modes(self):
        w = self.window
        host = Mock()
        rect = {'x': 0, 'y': 0, 'width': 880, 'height': 620, 'radius': 18}
        with patch.object(w, '_backdrop_host', host), patch.object(w, '_backdrop_native_rect', return_value=rect):
            w._composition_error = ''
            w._sync_sidebar_backdrop()
            self.assertEqual(host.update.call_args.args[0]['mode'], 'sidebar')
            w.full_window_backdrop = True
            w._sync_sidebar_backdrop()
            self.assertEqual(host.update.call_args.args[0]['mode'], 'full_window')
            w.full_window_backdrop = False

    def test_test_context_uses_cached_snapshot_without_extra_queries_and_navigates(self):
        w = self.window
        self.backend.runtime_status.reset_mock()
        w.discard_changes()
        self.assertIn('已放弃', w.feedback.text())
        w.change(size=48)
        self.assertEqual(w.feedback.text(), '')
        w.select_page(2)
        page = w.pages[2]
        self.assertIn('有未应用草稿', page.context_draft.text())
        self.assertIn('后台运行中', page.context_status.text())
        w.sync()
        page.runtime_link.click()
        self.assertEqual(w.stack.currentIndex(), 3)
        self.assertTrue(w.pages[3].pause_btn.hasFocus())
        w.select_page(2)
        page.appearance_link.click()
        self.assertEqual(w.stack.currentIndex(), 0)
        self.backend.runtime_status.assert_not_called()
        self.backend.apply.assert_not_called()
        self.assertEqual(w.draft().size, 48)

    def test_queued_titlebar_layout_does_not_outlive_its_window(self):
        from shiboken6 import isValid

        window = SafeMaterialWindow(self.backend)
        window.status_timer.stop()
        window._prewarm_timer.stop()
        window.preview.timer.stop()
        window.close()
        callback = Mock()
        window.title_bar._position_controls = callback
        try:
            window.title_bar.eventFilter(window.material_content, QEvent(QEvent.Type.LayoutRequest))
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            APP.processEvents()
            callback.assert_not_called()
            self.assertFalse(isValid(window))
        finally:
            if isValid(window):
                window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def test_size_and_adaptation_precede_palette_in_appearance_flow(self):
        w = self.window
        w.resize(1180, 800)
        APP.processEvents()
        self.assertLess(w.size_adaptation_group.mapTo(w.pages[0], QPoint()).y(),
                        w.palette_gallery.mapTo(w.pages[0], QPoint()).y())
        self.assertTrue(w.size_adaptation_group.isAncestorOf(w.pages[0].family_size.choice_buttons[0]))


if __name__ == '__main__':
    unittest.main()
