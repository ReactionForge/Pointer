import ctypes
from ctypes import wintypes
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch
import uuid

from scripts import shortcut_reader


class _NativeLink:
    """A Unicode COM fixture with real vtables and no filesystem or Shell writes."""
    target = 'C:\\安装包 验证\\Pointer 自定义安装\\Pointer.exe'
    icon = 'C:\\安装包 验证\\Pointer 自定义安装\\pointer.ico'

    def __init__(self, fail=None, initialized=0, null_interface=None):
        self.fail, self.null_interface = fail, null_interface
        self.calls, self.retained = [], []
        self.shell, self.shell_table = self._interface(21)
        self.persist, self.persist_table = self._interface(9)
        self._bind(self.shell_table, 0, self._query,
                   [ctypes.POINTER(shortcut_reader._GUID), ctypes.POINTER(ctypes.c_void_p)])
        self._bind(self.shell_table, 3, self._path,
                   [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD])
        self._bind(self.shell_table, 16, self._icon,
                   [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_int)])
        self._bind(self.persist_table, 5, self._load, [wintypes.LPCWSTR, wintypes.DWORD])
        self._bind(self.shell_table, 2, lambda _: self._release('shell'), [], wintypes.ULONG)
        self._bind(self.persist_table, 2, lambda _: self._release('persist'), [], wintypes.ULONG)
        self.ole = Mock()
        self.ole.CoInitialize.return_value = initialized
        self.ole.CoCreateInstance.side_effect = self._create

    def _interface(self, length):
        table = (ctypes.c_void_p * length)()
        instance = ctypes.pointer(ctypes.cast(table, ctypes.POINTER(ctypes.c_void_p)))
        self.retained.extend((table, instance))
        return ctypes.cast(instance, ctypes.c_void_p), table

    def _bind(self, table, slot, function, args, result=ctypes.c_long):
        callback = ctypes.WINFUNCTYPE(result, ctypes.c_void_p, *args)(function)
        self.retained.append(callback)
        table[slot] = ctypes.cast(callback, ctypes.c_void_p)

    def _result(self, stage):
        return -2147467259 if self.fail == stage else 0  # E_FAIL

    def _create(self, clsid, outer, context, iid, output):
        self.calls.append(('create', uuid.UUID(bytes_le=ctypes.string_at(clsid, 16)),
                           uuid.UUID(bytes_le=ctypes.string_at(iid, 16)), context, outer))
        if not self._result('create') and self.null_interface != 'shell':
            ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p))[0] = self.shell
        return self._result('create')

    def _query(self, this, iid, output):
        self.calls.append(('query', uuid.UUID(bytes_le=ctypes.string_at(iid, 16))))
        if not self._result('query') and self.null_interface != 'persist':
            output[0] = self.persist
        return self._result('query')

    def _load(self, this, path, mode):
        self.calls.append(('load', path, mode))
        return self._result('load')

    def _write(self, output, size, text):
        buffer = ctypes.create_unicode_buffer(text)
        if len(buffer) <= size:
            ctypes.memmove(output, buffer, ctypes.sizeof(buffer))

    def _path(self, this, output, size, data, flags):
        self.calls.append(('path', flags, data))
        self._write(output, size, self.target if self.fail != 'empty' else '')
        return 1 if self.fail == 'no_path' else self._result('path')

    def _icon(self, this, output, size, index):
        self.calls.append(('icon',))
        self._write(output, size, self.icon)
        index[0] = -17
        return self._result('icon')

    def _release(self, name):
        self.calls.append(('release', name))
        return 0

    def read(self):
        with patch.object(shortcut_reader.ctypes, 'WinDLL', return_value=self.ole):
            return shortcut_reader.read_shortcut(Path('中文链接.lnk'))


@unittest.skipUnless(sys.platform == 'win32', 'Windows COM ABI')
class ShortcutReaderTests(unittest.TestCase):
    def test_unicode_target_icon_and_negative_resource_index_are_preserved(self):
        link = _NativeLink()
        self.assertEqual(link.read(), {'target': link.target, 'icon': link.icon + ',-17'})
        self.assertEqual(link.calls[0][1:], (
            uuid.UUID('00021401-0000-0000-c000-000000000046'),
            uuid.UUID('000214f9-0000-0000-c000-000000000046'), 1, None))
        self.assertEqual(link.calls[1], ('query', uuid.UUID('0000010b-0000-0000-c000-000000000046')))
        self.assertEqual(link.calls[2], ('load', str(Path('中文链接.lnk').resolve()), 0x20))
        self.assertEqual(link.calls[3], ('path', 4, None))
        self.assertEqual([row[0] for row in link.calls],
                         ['create', 'query', 'load', 'path', 'icon', 'release', 'release'])
        self.assertEqual(link.calls[-2:], [('release', 'persist'), ('release', 'shell')])
        link.ole.CoUninitialize.assert_called_once_with()

    def test_s_false_initialization_is_balanced(self):
        link = _NativeLink(initialized=1)
        link.read()
        link.ole.CoUninitialize.assert_called_once_with()

    def test_existing_different_apartment_is_not_uninitialized(self):
        link = _NativeLink(initialized=-2147417850)
        link.read()
        link.ole.CoUninitialize.assert_not_called()

    def test_initialization_error_does_not_create_or_uninitialize(self):
        link = _NativeLink(initialized=-2147467259)
        with self.assertRaisesRegex(OSError, 'CoInitialize.*0x80004005'):
            link.read()
        link.ole.CoCreateInstance.assert_not_called()
        link.ole.CoUninitialize.assert_not_called()

    def test_hresult_failures_release_only_acquired_references(self):
        for stage, operation in [('create', 'CoCreateInstance'), ('query', 'QueryInterface'),
                                 ('load', 'Load'), ('path', 'GetPath'), ('icon', 'GetIconLocation')]:
            with self.subTest(stage=stage):
                link = _NativeLink(fail=stage)
                with self.assertRaisesRegex(OSError, operation + '.*0x80004005'):
                    link.read()
                expected = [] if stage == 'create' else [('release', 'shell')]
                if stage not in ('create', 'query'):
                    expected.insert(0, ('release', 'persist'))
                self.assertEqual([row for row in link.calls if row[0] == 'release'], expected)
                link.ole.CoUninitialize.assert_called_once_with()

    def test_s_false_and_empty_target_are_rejected(self):
        for stage in ('no_path', 'empty'):
            with self.subTest(stage=stage):
                link = _NativeLink(fail=stage)
                with self.assertRaisesRegex(OSError, 'no saved target'):
                    link.read()
                self.assertEqual(link.calls[-2:], [('release', 'persist'), ('release', 'shell')])
                self.assertNotIn(('icon',), link.calls)
                link.ole.CoUninitialize.assert_called_once_with()

    def test_null_success_interfaces_are_rejected_without_dereferencing_them(self):
        for interface in ('shell', 'persist'):
            with self.subTest(interface=interface):
                link = _NativeLink(null_interface=interface)
                with self.assertRaisesRegex(OSError, 'returned no'):
                    link.read()
                expected = [] if interface == 'shell' else [('release', 'shell')]
                self.assertEqual([row for row in link.calls if row[0] == 'release'], expected)
                link.ole.CoUninitialize.assert_called_once_with()
