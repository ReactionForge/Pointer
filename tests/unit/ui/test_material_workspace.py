"""Per-pixel alpha, accessibility fallback and own-window controls."""
import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import unittest
from unittest.mock import Mock,patch
from PySide6.QtCore import Qt,QPoint,QEvent,QCoreApplication
from PySide6.QtWidgets import QApplication,QFrame,QMessageBox
from PySide6.QtGui import QColor,QPalette
from PySide6.QtTest import QTest
from pointer.cursor.settings import CursorSettings
from pointer.ui.confirmations import confirmation_box
from pointer.ui.approved_workspace import approved_colors
from scripts.capture_material_ui import SafeMaterialWindow
from scripts.safe_preview import isolated_update_services
APP=QApplication.instance() or QApplication([])
class MaterialWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.backend=Mock();self.backend.settings.return_value=CursorSettings(tray_enabled=False,auto_check_update=False)
        self.backend.backend.snapshot.return_value={'running':False,'startup_enabled':False}
        self.window=SafeMaterialWindow(self.backend);self.window.status_timer.stop();self.window._prewarm_timer.stop();self.window.preview.timer.stop()
        self.window.show();APP.processEvents();APP.processEvents()
    def tearDown(self):
        self.window.discard_changes();self.window.close()
    def test_alpha_partition_toggle_and_inactive_fallback(self):
        w=self.window
        self.assertTrue(w.testAttribute(Qt.WidgetAttribute.WA_TranslucentBackground))
        self.assertTrue(w.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertEqual(w.windowOpacity(),1)
        for dark,alpha in ((True,184),(False,208)):
            if w.ui_dark!=dark:w.toggle_workspace_theme()
            QCoreApplication.sendEvent(w,QEvent(QEvent.Type.WindowActivate));APP.processEvents()
            image=w.grab().toImage()
            self.assertEqual(image.pixelColor(50,400).alpha(),alpha)
            self.assertEqual(image.pixelColor(400,700).alpha(),255)
            w.set_sidebar_transparent(False);APP.processEvents()
            self.assertEqual(w.grab().toImage().pixelColor(50,400).alpha(),255)
            w.set_sidebar_transparent(True)
            QCoreApplication.sendEvent(w,QEvent(QEvent.Type.WindowDeactivate));APP.processEvents()
            self.assertEqual(w.grab().toImage().pixelColor(50,400).alpha(),255)
        self.backend.apply.assert_not_called()
    def test_two_pages_geometry_narrow_observation_no_overlap_and_fixed_footer(self):
        w=self.window;original=w.draft()
        for width,height in ((880,620),(1180,880),(1360,920)):
            w.resize(width,height)
            for page in (0,3):
                w.select_page(page);APP.processEvents();APP.processEvents()
                self.assertEqual((w.width(),w.height()),(width,height))
                scroll=w.stack.widget(page)
                self.assertEqual(scroll.horizontalScrollBar().maximum(),0)
                self.assertEqual(w.findChild(QFrame,'controlBar').height(),64)
                self.assertTrue(w.apply_button.isVisible())
                if page==0:
                    before=w.preview.mapTo(w,QPoint())
                    scroll.verticalScrollBar().setValue(scroll.verticalScrollBar().maximum());APP.processEvents()
                    self.assertEqual(before,w.preview.mapTo(w,QPoint()))
                    form=w.preview.layout();last=-1
                    for index in range(form.count()):
                        item=form.itemAt(index)
                        if item.spacerItem() or (item.widget() and not item.widget().isVisible()):continue
                        bounds=item.geometry()
                        self.assertGreaterEqual(bounds.top(),last,f'Overlapping observation at {width}: {index}')
                        last=bounds.bottom()
                self.assertEqual(w.draft(),original)
    def test_controls_keyboard_move_resize_cancel_and_system_dispatch(self):
        w=self.window;handle=w.windowHandle()
        with patch.object(handle,'startSystemMove',return_value=True) as move:
            QTest.mousePress(w.title_bar,Qt.MouseButton.LeftButton,pos=QPoint(12,12))
            QTest.mouseRelease(w.title_bar,Qt.MouseButton.LeftButton,pos=QPoint(12,12));move.assert_called_once()
        points=[(QPoint(1,1),Qt.Edge.LeftEdge|Qt.Edge.TopEdge),(QPoint(w.width()-1,1),Qt.Edge.RightEdge|Qt.Edge.TopEdge),
          (QPoint(1,w.height()-1),Qt.Edge.LeftEdge|Qt.Edge.BottomEdge),(QPoint(w.width()-1,w.height()-1),Qt.Edge.RightEdge|Qt.Edge.BottomEdge),
          (QPoint(1,300),Qt.Edge.LeftEdge),(QPoint(w.width()-1,300),Qt.Edge.RightEdge),(QPoint(300,1),Qt.Edge.TopEdge),(QPoint(300,w.height()-1),Qt.Edge.BottomEdge)]
        for point,edge in points:self.assertEqual(w.resize_edges(point),edge)
        with patch.object(handle,'startSystemResize',return_value=True) as resize:
            QTest.mousePress(w.centralWidget(),Qt.MouseButton.LeftButton,pos=QPoint(1,300))
            QTest.mouseRelease(w.centralWidget(),Qt.MouseButton.LeftButton,pos=QPoint(1,300));resize.assert_called_once_with(Qt.Edge.LeftEdge)
        original=w.geometry();w.begin_keyboard_operation('move');QTest.keyClick(w,Qt.Key.Key_Right)
        self.assertEqual(w.x(),original.x()+8);QTest.keyClick(w,Qt.Key.Key_Escape);self.assertEqual(w.geometry(),original)
        w.begin_keyboard_operation('resize');QTest.keyClick(w,Qt.Key.Key_Right);self.assertEqual(w.width(),original.width()+8)
        QTest.keyClick(w,Qt.Key.Key_Escape);self.assertEqual(w.geometry(),original)
        w.toggle_maximized();self.assertTrue(w.isMaximized());self.assertFalse(w.resize_edges(QPoint(1,1)))
        w.toggle_maximized();self.assertFalse(w.isMaximized())
        self.assertEqual(len(w.system_menu.actions()),6)
        self.assertEqual(set(w.title_bar.buttons),{'最小化','最大化或还原','关闭'})
    def test_updates_and_owned_confirmations_stay_isolated(self):
        w=self.window
        with isolated_update_services(),patch('pointer.updater.check_for_updates') as check:
            w.select_page(3);w.pages[3].check_update_btn.click();w._check_update_silent_startup();w._show_update_dialog({'available':True})
            check.assert_not_called();self.assertEqual(w._threads,[])
        original=APP.palette()
        try:
            for system_dark in (True,False):
                palette=QPalette(original);palette.setColor(QPalette.ColorRole.Window,QColor('#202020' if system_dark else '#ffffff'));APP.setPalette(palette)
                for dark in (True,False):
                    if w.ui_dark!=dark:w.toggle_workspace_theme()
                    box=confirmation_box(w,'未应用修改','继续编辑？','放弃修改','继续编辑')
                    self.assertEqual(box.palette().color(QPalette.ColorRole.Window).name(),approved_colors(dark)['canvas'])
                    self.assertIs(box.defaultButton(),box.button(QMessageBox.StandardButton.No));self.assertIs(box.escapeButton(),box.button(QMessageBox.StandardButton.No));box.deleteLater()
        finally:APP.setPalette(original)
        for name in ('apply','pause','resume','restore','set_startup'):getattr(self.backend,name).assert_not_called()

    def test_live_composed_cursor_layers_in_new_rounded_surfaces(self):
        w=self.window;w.preview.timer.start();w.pages[0].open_advanced()
        for dark in (False,True,False):
            if w.ui_dark!=dark:w.toggle_workspace_theme()
            for width,height in ((880,620),(1180,880)):
                w.resize(width,height);w.change(size=64);QTest.qWait(60)
                image=w.grab().toImage()
                for surface in w.preview.surfaces:
                    origin=surface.mapTo(w,QPoint());bounds=surface.cursor_bounds.toRect().translated(origin).adjusted(20,20,-20,-20)
                    background=QColor('#eef0f5' if surface.theme=='light' else '#202329')
                    count=sum(image.pixelColor(x,y)!=background for y in range(bounds.top(),bounds.bottom()+1) for x in range(bounds.left(),bounds.right()+1))
                    self.assertGreater(count,20)
                    self.assertTrue(surface.rect().contains(surface.cursor_bounds.toRect()))
                last=-1
                for index in range(w.preview.layout().count()):
                    item=w.preview.layout().itemAt(index)
                    if item.spacerItem() or (item.widget() and not item.widget().isVisible()):continue
                    bounds=item.geometry();self.assertGreaterEqual(bounds.top(),last);last=bounds.bottom()
    def test_unsupported_high_contrast_or_disabled_transparency_policy_is_opaque(self):
        policy={'supported':False,'high_contrast':True,'system_transparency':False,'reason':'simulated fallback'}
        w=SafeMaterialWindow(self.backend,policy=policy);w.status_timer.stop();w._prewarm_timer.stop();w.preview.timer.stop();w.show()
        try:
            APP.processEvents();APP.processEvents()
            self.assertFalse(w.alpha_toggle.isEnabled());self.assertFalse(w.sidebar_transparent)
            w.set_sidebar_transparent(True);self.assertFalse(w.sidebar_transparent)
            self.assertEqual(w.grab().toImage().pixelColor(50,400).alpha(),255)
        finally:w.close()

    def test_system_menu_normal_maximized_restored_states_and_escape_cancel(self):
        w=self.window
        def menu_state():
            w.show_system_menu();APP.processEvents()
            result=[action.isEnabled() for action in w.system_menu.actions()]
            QTest.keyClick(w.system_menu,Qt.Key.Key_Escape);APP.processEvents()
            return result
        self.assertEqual(menu_state(),[False,True,True,True,True,True])
        w.showMaximized();APP.processEvents()
        self.assertTrue(w.isMaximized())
        self.assertEqual(menu_state(),[True,False,False,True,False,True])
        self.assertTrue(w.isMaximized());self.assertIsNone(w._keyboard_operation)
        w.showNormal();APP.processEvents()
        self.assertFalse(w.isMaximized())
        self.assertEqual(menu_state(),[False,True,True,True,True,True])
        for mode,index in (('move',1),('resize',2)):
            original=w.geometry()
            w.show_system_menu();APP.processEvents()
            w.system_menu.actions()[index].trigger();w.system_menu.hide();APP.processEvents()
            self.assertEqual(w._keyboard_operation[0],mode)
            QTest.keyClick(w,Qt.Key.Key_Right)
            self.assertNotEqual(w.geometry(),original)
            QTest.keyClick(w,Qt.Key.Key_Escape)
            self.assertEqual(w.geometry(),original);self.assertFalse(w.isMaximized())
            self.assertIsNone(w._keyboard_operation)
        for name in ('apply','pause','resume','restore','set_startup'):getattr(self.backend,name).assert_not_called()
