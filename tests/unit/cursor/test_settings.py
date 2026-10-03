"""Preferences reject invalid input without touching saved settings or Windows."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class SettingsTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('pointer.cursor.settings'), 'Settings API missing')
        from pointer.cursor.settings import CursorSettings, SettingsStore
        self.Settings, self.Store = CursorSettings, SettingsStore
        self.folder = tempfile.TemporaryDirectory(prefix='Pointer 配置 ')
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)

    def test_defaults_and_roundtrip(self):
        store = self.Store(self.root)
        settings = self.Settings()
        self.assertEqual((settings.size, settings.strength, settings.press_ms, settings.release_ms), (32, 50, 60, 150))
        store.save(settings)
        self.assertEqual(store.load(), settings)

    def test_migration_preserves_actual_startup_and_shrink(self):
        legacy = self.root / 'click-motion-settings.json'
        legacy.write_text('{"mode":"shrink"}')
        store = self.Store(self.root)
        migrated = store.load(legacy, startup_enabled=True)
        self.assertEqual((migrated.motion, migrated.startup), ('shrink', True))
        self.assertEqual(store.load(legacy, False), migrated)

    def test_invalid_preferences_rejected(self):
        for changes in ({'size': 31}, {'size': True}, {'strength': -1}, {'strength': 101},
                        {'press_ms': 39}, {'press_ms': 201}, {'release_ms': 79},
                        {'release_ms': 401}, {'schema_version': 2}, {'startup': 1},
                        {'motion': 'other'}, {'appearance': 'other'},
                        {'light_body': '#xyz000'}, {'dark_outline': '#fff'}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.Settings.from_dict({'schema_version': 1, **changes})

    def test_direct_constructor_is_validated(self):
        with self.assertRaises(ValueError):
            self.Settings(size=999)
        self.assertEqual(self.Settings(light_body='#ABCDEF').light_body, '#abcdef')

    def test_corrupt_existing_file_is_preserved(self):
        store = self.Store(self.root)
        store.path.write_bytes(b'{broken')
        with self.assertRaises(ValueError):
            store.load()
        self.assertEqual(store.path.read_bytes(), b'{broken')

    def test_invalid_import_never_changes_previous_settings(self):
        store = self.Store(self.root)
        store.save(self.Settings(motion='shrink'))
        before = store.path.read_bytes()
        path = self.root / 'incoming.json'
        for content in ('[]', '{"schema_version":99}', '{"schema_version":1,"size":999}',
                        '{"schema_version":1,"machine_path":"secret"}', 'x' * 65537):
            path.write_text(content)
            with self.assertRaises(ValueError):
                store.import_file(path)
            self.assertEqual(store.path.read_bytes(), before)

    def test_valid_import_returns_draft_and_export_contains_only_settings(self):
        store = self.Store(self.root)
        saved, draft = self.Settings(), self.Settings(strength=75, motion='off')
        store.save(saved)
        target = self.root / 'export.json'
        store.export_file(target, draft)
        self.assertEqual(store.import_file(target), draft)
        self.assertEqual(store.load(), saved)
        self.assertEqual(json.loads(target.read_text()), draft.to_dict())

    def test_failed_atomic_replace_keeps_previous_file(self):
        store = self.Store(self.root)
        store.save(self.Settings())
        before = store.path.read_bytes()
        with patch('pointer.cursor.settings.os.replace', side_effect=PermissionError('locked')):
            with self.assertRaises(PermissionError):
                store.save(self.Settings(size=48))
        self.assertEqual(store.path.read_bytes(), before)
        self.assertEqual(list(self.root.glob('*.tmp')), [])
