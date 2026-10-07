import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from pointer.cursor.settings import CursorSettings
from pointer.ui.main_window import MainWindow

QT_APP = QApplication.instance() or QApplication([])


class FamilyWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.application = Mock()
        self.application.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        self.application.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        self.window = MainWindow(self.application)

    def tearDown(self):
        self.window.discard_changes()
        self.window.close()

    def test_observation_background_and_role_never_change_draft(self):
        self.assertTrue(hasattr(self.window.preview, 'background'), 'Independent preview background control missing')
        before = self.window.draft().to_dict()
        panel = self.window.preview
        panel.background.setCurrentIndex(panel.background.findData('dark'))
        panel.role.setCurrentIndex(panel.role.findData('move'))
        self.assertEqual(self.window.draft().to_dict(), before)
        self.assertTrue(panel.surfaces[0].isHidden())
        self.assertFalse(panel.surfaces[1].isHidden())
        self.assertEqual(panel.role.currentData(), 'move')

    def test_leaving_preview_clears_temporary_press(self):
        panel = self.window.preview
        panel.set_down(True)
        panel.surfaces[0].pressed = True
        self.window.select_page(3)
        self.assertFalse(panel.down)
        self.assertFalse(panel.surfaces[0].pressed)

    def test_shape_choice_is_draft_backed_and_apply_stays_reachable(self):
        page = self.window.pages[0]
        self.assertTrue(hasattr(page, 'shape_buttons'), 'Shared family shape shelf missing')
        page.shape_buttons['facet'].click()
        self.assertEqual(self.window.draft().style, 'facet')
        self.assertNotEqual(self.window.draft(), self.window.applied)
        self.window.resize(880, 620)
        self.window.show()
        QT_APP.processEvents()
        self.assertTrue(self.window.apply_button.isVisible())
        self.assertTrue(self.window.apply_button.isEnabled())
        self.assertTrue(self.window.rect().contains(self.window.apply_button.mapTo(self.window, self.window.apply_button.rect().center())))

    def test_focus_loss_releases_preview_press(self):
        from PySide6.QtCore import QEvent
        self.window.preview.set_down(True)
        QApplication.sendEvent(self.window, QEvent(QEvent.Type.WindowDeactivate))
        self.assertFalse(self.window.preview.down)

    def test_motion_specimens_keep_a_stable_coordinate_frame(self):
        from pointer.ui.family_workspace import cursor_pixmap
        settings = CursorSettings(size=64)
        neutral = cursor_pixmap(settings, 'arrow', 'light', 0)
        for frame in range(1, 5):
            self.assertEqual(cursor_pixmap(settings, 'arrow', 'light', frame).size(), neutral.size())

    def test_every_role_renders_and_background_strategy_remains_independent(self):
        panel = self.window.preview
        self.window.change(appearance='light')
        panel.background.setCurrentIndex(panel.background.findData('dark'))
        self.window.show()
        for index in range(panel.role.count()):
            panel.role.setCurrentIndex(index)
            QT_APP.processEvents()
            self.assertFalse(panel.grab().isNull())
        self.assertEqual(panel.role.count(), 17)
        self.assertEqual(self.window.draft().appearance, 'light')

    def test_narrow_window_can_scroll_to_all_shared_controls(self):
        self.window.resize(880, 620)
        self.window.show()
        QT_APP.processEvents()
        scroll = self.window.stack.widget(0)
        page = self.window.pages[0]
        scroll.ensureWidgetVisible(page.family_size)
        QT_APP.processEvents()
        center = page.family_size.mapTo(scroll.viewport(), page.family_size.rect().center())
        self.assertTrue(scroll.viewport().rect().contains(center))
        self.assertTrue(self.window.apply_button.isVisible())
        page.open_advanced()
        QT_APP.processEvents()
        self.assertTrue(page.inline_colors.isVisible())
        self.window.busy = True
        self.window.sync()
        self.assertFalse(page.inline_colors.isEnabled())
        self.window.busy = False
        page.reset_color_session()
