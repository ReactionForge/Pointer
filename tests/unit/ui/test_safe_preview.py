import os
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication
from pointer.cursor.settings import CursorSettings
from scripts.safe_preview import SafePreviewWindow, isolated_update_services, ISOLATED_UPDATE_MESSAGE

APP = QApplication.instance() or QApplication([])


class SafePreviewTests(unittest.TestCase):
    def test_all_provided_mock_entry_points_use_guarded_window_and_service_context(self):
        import importlib
        for name in ('capture_commercial_ui', 'capture_family_ui', 'capture_design_review', 'capture_art_candidate', 'capture_motion_review', 'capture_reference_ui', 'capture_approved_ui', 'capture_dual_ui', 'capture_material_ui'):
            entry = importlib.import_module('scripts.' + name)
            self.assertIs(entry.SafePreviewWindow, SafePreviewWindow)
            self.assertTrue(hasattr(entry.main, '__wrapped__'))

    def test_settings_button_and_update_callbacks_never_reach_services_or_network(self):
        targets = ('pointer.updater.check_for_updates',
                   'pointer.updater.download_update_package',
                   'pointer.updater.trigger_silent_upgrade',
                   'pointer.ui.update_dialog.download_update_package',
                   'pointer.ui.update_dialog.trigger_silent_upgrade',
                   'pointer.ui.update_dialog.UpdateDialog', 'urllib.request.urlopen')
        backend = Mock()
        backend.settings.return_value = CursorSettings(tray_enabled=False, auto_check_update=False)
        backend.backend.snapshot.return_value = {'running': False, 'startup_enabled': False}
        with ExitStack() as stack:
            calls = [stack.enter_context(patch(target)) for target in targets]
            window = SafePreviewWindow(backend)
            window.show()
            window.select_page(3)
            window.pages[3].check_update_btn.click()
            window.check_updates_interactive()
            window._check_update_silent_startup()
            window._show_update_dialog({'available': True, 'download_url': 'https://invalid.example/installer.exe'})
            APP.processEvents()
            self.assertEqual(window.feedback.text(), ISOLATED_UPDATE_MESSAGE)
            self.assertEqual(window.pages[3].update_status_lbl.text(), ISOLATED_UPDATE_MESSAGE)
            self.assertTrue(window.pages[3].check_update_btn.isEnabled())
            self.assertEqual(window._threads, [])
            for call in calls:
                call.assert_not_called()
            backend.apply.assert_not_called()
            window.close()

    def test_update_service_guard_blocks_direct_download_and_restores_original_functions(self):
        from pointer import updater
        from pointer.ui import update_dialog
        original = updater.check_for_updates
        with patch('urllib.request.urlopen') as network, isolated_update_services():
            for callback in (updater.check_for_updates, updater.download_update_package,
                             updater.trigger_silent_upgrade, update_dialog.download_update_package,
                             update_dialog.trigger_silent_upgrade):
                with self.assertRaisesRegex(RuntimeError, '隔离预览'):
                    callback()
            network.assert_not_called()
        self.assertIs(updater.check_for_updates, original)
