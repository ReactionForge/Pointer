"""Production entry preserves IPC while selecting the approved Material window."""
import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from pointer.ui import main_window

APP = QApplication.instance() or QApplication([])


class ReleaseEntryTests(unittest.TestCase):
    def test_default_launch_uses_material_persistent_data_and_stops_helper_before_mutex(self):
        order = []
        app = Mock()
        app.platformName.return_value = 'windows'
        app.exec.return_value = 0
        instance = Mock(primary=True)
        instance.close.side_effect = lambda: order.append('mutex')
        application = Mock()
        window = Mock()
        window._backdrop_host.shutdown.side_effect = lambda: order.append('helper')
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory)
            helper = data / 'prepared-helper.exe'
            with patch.object(main_window, 'QApplication', instance=Mock(return_value=app)), \
                 patch('pointer.windows.gui_ipc.WindowInstance', return_value=instance), \
                 patch('pointer.windows.gui_ipc.read_request', return_value=None), \
                 patch('pointer.application.Application', return_value=application), \
                 patch('pointer.ui.material_workspace.MaterialWindow', return_value=window) as factory, \
                 patch('pointer.windows.composition_host.prepare_helper', return_value=helper) as prepare, \
                 patch.object(main_window, 'DATA_ROOT', data):
                self.assertEqual(main_window.launch(test_page=True), 0)
            factory.assert_called_once()
            args, fields = factory.call_args
            self.assertEqual(args, (application,))
            self.assertEqual(fields['sidebar_store'].path, data / 'sidebar-appearance.json')
            self.assertEqual(fields['composition_helper'], helper)
            self.assertIsNone(fields['composition_error'])
            prepare.assert_called_once_with(data / 'composition-cache')
            window.select_page.assert_called_once_with(2)
            window.start_preset_prewarm.assert_called_once()
            self.assertEqual(order, ['helper', 'mutex'])
            for action in ('apply', 'pause', 'resume', 'restore', 'set_startup'):
                getattr(application, action).assert_not_called()

    def test_upgrade_readiness_includes_saved_window_appearance(self):
        window = Mock(busy=False, sidebar_dirty=False, applied='cursor-draft')
        window.draft.return_value = 'cursor-draft'
        self.assertTrue(main_window._ready_for_upgrade(window))
        window.sidebar_dirty = True
        self.assertFalse(main_window._ready_for_upgrade(window))
        window.sidebar_dirty = False
        window.busy = True
        self.assertFalse(main_window._ready_for_upgrade(window))
