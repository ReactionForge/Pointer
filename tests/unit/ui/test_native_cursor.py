import importlib.util
import unittest
from unittest.mock import patch


class NativeCursorTests(unittest.TestCase):
    def test_shared_system_handle_used_without_copy(self):
        self.assertIsNotNone(importlib.util.find_spec('pointer.ui'), 'Native filter missing')
        from pointer.ui.native_cursor import NativeCursorFilter
        with patch('pointer.ui.native_cursor.load_system_cursor', return_value=1234) as load, \
             patch('pointer.ui.native_cursor.set_system_cursor') as assign:
            NativeCursorFilter().show_role('hand')
            load.assert_called_once_with('hand')
            assign.assert_called_once_with(1234)
