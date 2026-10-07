"""The backdrop helper protocol stays asynchronous, bounded and window-specific."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
import unittest
from unittest.mock import patch
from PySide6.QtCore import QObject, QProcess, Signal
from PySide6.QtTest import QTest, QSignalSpy
from PySide6.QtWidgets import QApplication


APP = QApplication.instance() or QApplication([])


class ProcessFixture(QObject):
    readyReadStandardOutput = Signal()
    readyReadStandardError = Signal()
    finished = Signal(int, object)
    errorOccurred = Signal(object)

    def __init__(self):
        super().__init__()
        self.launches = []
        self.writes = []
        self.output = b''
        self.status = QProcess.ProcessState.NotRunning
        self.kills = 0
        self.eof_sent = False
        self.launch_error = False
        self.waits = []
        self.wait_results = []
        self.kill_finishes = True

    def start(self, program, arguments):
        self.launches.append((program, arguments))
        self.status = QProcess.ProcessState.Running
        if self.launch_error:
            self.status = QProcess.ProcessState.NotRunning
            self.errorOccurred.emit(QProcess.ProcessError.FailedToStart)

    def state(self):
        return self.status

    def write(self, data):
        self.writes.append(bytes(data))
        return len(data)

    def closeWriteChannel(self):
        self.eof_sent = True

    def kill(self):
        self.kills += 1
        if self.kill_finishes:
            self.finish()

    def waitForFinished(self, timeout):
        self.waits.append(timeout)
        if self.status == QProcess.ProcessState.NotRunning:
            return True
        if self.wait_results and self.wait_results.pop(0):
            self.finish()
            return True
        return False

    def errorString(self):
        return 'fixture cannot launch helper'

    def readAllStandardOutput(self):
        value, self.output = self.output, b''
        return value

    def readAllStandardError(self):
        return b''

    def feed(self, data):
        self.output += data if isinstance(data, bytes) else (json.dumps(data) + '\n').encode()
        self.readyReadStandardOutput.emit()

    def finish(self):
        self.status = QProcess.ProcessState.NotRunning
        self.finished.emit(0, QProcess.ExitStatus.NormalExit)

    def messages(self):
        return [json.loads(line) for line in self.writes]


class CompositionHostTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec('pointer.windows.composition_host'),
                             'Composition helper controller missing')
        from pointer.windows.composition_host import CompositionHost
        self.process = ProcessFixture()
        self.host = CompositionHost('owned-helper.exe', process_factory=lambda parent: self.process,
                                    handshake_ms=1000, apply_ms=1000, shutdown_ms=20)
        self.failures = []
        self.readiness = []
        self.host.failed.connect(self.failures.append)
        self.host.ready_changed.connect(self.readiness.append)
        self.state = dict(visible=True, x=-120, y=20, width=200, height=700, radius=16, sigma=24.0)

    def tearDown(self):
        if hasattr(self, 'host'):
            self.host.close()
            self.process.finish()
            self.host.deleteLater()
            APP.processEvents()

    def ready(self):
        self.process.feed(dict(event='ready', protocol=1, pid=os.getpid(), hwnd=12345))

    def test_start_is_idempotent_and_queues_only_latest_state_until_ready(self):
        self.host.start(12345)
        self.host.start(12345)
        self.host.update(self.state)
        self.state['sigma'] = 36.0
        self.host.update(self.state)
        self.assertEqual(self.process.writes, [])
        self.ready()
        self.assertTrue(self.host.ready)
        self.assertEqual(self.readiness, [True])
        self.assertEqual(len(self.process.launches), 1)
        self.assertEqual(self.process.launches[0][1], ['--pid', str(os.getpid()), '--hwnd', '12345'])
        self.assertEqual(self.process.messages(), [dict(self.state, seq=2)])

    def test_applied_ack_flushes_latest_update_without_mutating_caller_state(self):
        self.host.start(12345)
        self.ready()
        self.host.update(self.state)
        self.host.update(dict(self.state, sigma=8.0))
        self.host.update(dict(self.state, sigma=40.0))
        self.state['visible'] = False
        self.assertEqual(len(self.process.writes), 1)
        self.process.feed(dict(event='applied', seq=1))
        self.assertEqual(self.process.messages()[1], dict(visible=True, x=-120, y=20,
                         width=200, height=700, radius=16, sigma=40.0, seq=3))
        self.assertFalse(self.state['visible'])

    def test_ready_callback_replaces_pending_state_without_duplicate_write(self):
        self.host.start(12345)
        self.host.update(self.state)
        self.host.ready_changed.connect(lambda ready: self.host.update(dict(self.state, sigma=36.0)) if ready else None)
        self.ready()
        self.assertEqual(self.process.messages(), [dict(self.state, sigma=36.0, seq=2)])
        self.process.feed(dict(event='applied', seq=2))
        self.assertEqual(len(self.process.writes), 1)
        self.assertTrue(self.host.ready)

    def test_ready_identity_and_types_must_match_the_requested_window(self):
        self.host.start(12345)
        self.process.feed(dict(event='ready', protocol=True, pid=os.getpid(), hwnd=12345))
        self.assertFalse(self.host.ready)
        self.assertTrue(self.failures)
        self.assertEqual(self.process.messages(), [dict(command='quit')])

    def test_wrong_hwnd_never_enables_the_effect(self):
        self.host.start(12345)
        self.process.feed(dict(event='ready', protocol=1, pid=os.getpid(), hwnd=54321))
        self.assertFalse(self.host.ready)
        self.assertTrue(self.failures)

    def test_partial_utf8_lines_are_buffered_and_unknown_messages_fail_closed(self):
        self.host.start(12345)
        data = (json.dumps(dict(event='ready', protocol=1, pid=os.getpid(), hwnd=12345)) + '\n').encode()
        self.process.feed(data[:18])
        self.assertFalse(self.host.ready)
        self.process.feed(data[18:])
        self.assertTrue(self.host.ready)
        self.process.feed(dict(event='run', command='external-action'))
        self.assertFalse(self.host.ready)
        self.assertEqual(self.readiness, [True, False])
        self.assertTrue(self.failures)

    def test_oversized_protocol_line_is_rejected(self):
        self.host.start(12345)
        self.process.feed(b'x' * 4097)
        self.assertFalse(self.host.ready)
        self.assertTrue(self.failures)

    def test_protocol_buffer_overflow_fails_without_processing_any_messages(self):
        self.host.start(12345)
        self.process.feed(b'{}\n' * 22000)
        self.assertFalse(self.host.ready)
        self.assertIn('64 KiB', self.host.last_error)

    def test_helper_error_turns_off_the_effect_and_preserves_its_reason(self):
        self.host.start(12345)
        self.ready()
        self.process.feed(dict(event='error', code='composition-unavailable', message='DWM refused target'))
        self.assertFalse(self.host.ready)
        self.assertIn('DWM refused target', self.host.last_error)
        self.assertEqual(self.readiness, [True, False])

    def test_process_failure_and_eof_disable_ready_without_changing_settings(self):
        original = dict(self.state)
        self.host.start(12345)
        self.ready()
        self.host.update(self.state)
        self.process.finish()
        self.assertFalse(self.host.ready)
        self.assertEqual(self.state, original)
        self.assertEqual(self.readiness, [True, False])
        self.assertTrue(self.failures)

    def test_start_failure_is_reported_without_waiting_for_a_timeout(self):
        self.process.launch_error = True
        self.assertFalse(self.host.start(12345))
        self.assertFalse(self.host.ready)
        self.assertEqual(len(self.failures), 1)

    def test_close_is_idempotent_and_only_kills_its_own_process_after_grace_period(self):
        self.host.start(12345)
        self.ready()
        finished = QSignalSpy(self.process.finished)
        self.host.close()
        self.host.close()
        self.assertFalse(self.host.ready)
        self.assertEqual(self.process.messages(), [dict(command='quit')])
        self.assertTrue(self.process.eof_sent)
        self.assertEqual(self.process.kills, 0)
        self.assertTrue(finished.wait(1000), 'Owned process never finished after the grace period')
        self.assertEqual(self.process.kills, 1)
        self.assertEqual(finished.count(), 1)
        self.assertEqual(self.failures, [])

    def test_shutdown_waits_for_graceful_exit_before_returning(self):
        self.host.start(12345)
        self.ready()
        self.process.wait_results = [True]
        self.assertTrue(self.host.shutdown())
        self.assertEqual(self.process.state(), QProcess.ProcessState.NotRunning)
        self.assertFalse(self.host.ready)
        self.assertEqual(self.process.messages(), [dict(command='quit')])
        self.assertTrue(self.process.eof_sent)
        self.assertEqual(self.process.waits, [20])
        self.assertEqual(self.process.kills, 0)
        self.assertEqual(self.failures, [])
        self.assertTrue(self.host.shutdown())
        QTest.qWait(40)
        self.assertEqual(self.process.waits, [20])
        self.assertEqual(self.process.kills, 0)
        self.assertEqual(self.process.messages(), [dict(command='quit')])

    def test_shutdown_kills_only_its_owned_process_after_bounded_wait(self):
        unrelated = ProcessFixture()
        unrelated.start('other-helper.exe', [])
        try:
            self.host.start(12345)
            self.ready()
            self.assertTrue(self.host.shutdown())
            self.assertEqual(self.process.state(), QProcess.ProcessState.NotRunning)
            self.assertEqual(self.process.waits, [20, 20])
            self.assertEqual(self.process.kills, 1)
            self.assertEqual(self.process.messages(), [dict(command='quit')])
            self.assertTrue(self.process.eof_sent)
            self.assertEqual(unrelated.state(), QProcess.ProcessState.Running)
            self.assertEqual(unrelated.kills, 0)
            self.assertEqual(unrelated.waits, [])
            self.assertEqual(unrelated.writes, [])
            self.assertTrue(self.host.shutdown())
            self.assertEqual(self.process.waits, [20, 20])
            self.assertEqual(self.process.kills, 1)
            self.assertEqual(self.failures, [])
        finally:
            unrelated.finish()
            unrelated.deleteLater()

    def test_shutdown_reports_when_owned_process_has_not_exited_after_kill(self):
        self.host.start(12345)
        self.ready()
        self.process.kill_finishes = False
        self.assertFalse(self.host.shutdown())
        self.assertEqual(self.process.state(), QProcess.ProcessState.Running)
        self.assertEqual(self.process.waits, [20, 20])
        self.assertEqual(self.process.kills, 1)
        QTest.qWait(40)
        self.assertEqual(self.process.kills, 1)

    def test_shutdown_before_start_does_not_launch_or_wait_for_a_process(self):
        self.assertTrue(self.host.shutdown())
        self.assertTrue(self.host.shutdown())
        self.assertEqual(self.process.launches, [])
        self.assertEqual(self.process.writes, [])
        self.assertEqual(self.process.waits, [])
        self.assertEqual(self.process.kills, 0)

    def test_default_controller_does_not_launch_native_from_offscreen(self):
        from pointer.windows.composition_host import CompositionHost
        host = CompositionHost('owned-helper.exe')
        try:
            self.assertFalse(host.start(12345))
            self.assertFalse(host.ready)
        finally:
            host.close()
            host.deleteLater()

    def test_invalid_state_is_rejected_before_any_helper_write(self):
        self.host.start(12345)
        self.ready()
        for fields in (dict(width=0), dict(visible=1), dict(sigma=float('nan')), dict(hwnd=54321)):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.host.update(dict(self.state, **fields))
        self.assertEqual(self.process.writes, [])

    def test_handshake_timeout_fails_asynchronously(self):
        self.host._handshake_timer.setInterval(5)
        failed = QSignalSpy(self.host.failed)
        self.host.start(12345)
        self.assertEqual(self.failures, [])
        self.assertTrue(failed.wait(1000), 'Handshake timeout signal was not delivered')
        self.assertFalse(self.host.ready)
        self.assertEqual(failed.count(), 1)
        self.assertIn('ready timeout', self.host.last_error)
        self.assertEqual(self.process.messages(), [dict(command='quit')])
        self.assertTrue(self.process.eof_sent)

    def test_missing_apply_ack_fails_asynchronously(self):
        self.host._apply_timer.setInterval(5)
        failed = QSignalSpy(self.host.failed)
        self.host.start(12345)
        self.ready()
        self.host.update(self.state)
        self.assertEqual(self.failures, [])
        self.assertTrue(failed.wait(1000), 'Apply timeout signal was not delivered')
        self.assertFalse(self.host.ready)
        self.assertEqual(failed.count(), 1)
        self.assertIn('apply timeout', self.host.last_error)

    def test_prepare_cache_reuses_the_binary_until_helper_sources_change(self):
        import pointer.windows.composition_host as module
        self.assertTrue(callable(getattr(module, 'prepare_helper', None)), 'Helper compiler missing')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'Sidecar.cs'
            source.write_text('original helper source', encoding='utf8')
            compiler = folder / 'csc.exe'
            compiler.write_bytes(b'installed compiler fixture')
            builds = []
            def compile_helper(arguments, **kwargs):
                builds.append(arguments)
                binary = Path(next(value[5:] for value in arguments if value.startswith('/out:')))
                binary.write_bytes(b'MZ compiled fixture')
                return subprocess.CompletedProcess(arguments, 0, b'', b'')
            with patch.object(module.sys, 'platform', 'win32'), \
                 patch.object(module, '_compiler_inputs', return_value=(compiler, [source], [])), \
                 patch.object(module.subprocess, 'run', side_effect=compile_helper):
                first = module.prepare_helper(folder / 'cache')
                second = module.prepare_helper(folder / 'cache')
                self.assertEqual(first, second)
                self.assertEqual(len(builds), 1)
                source.write_text('changed helper source', encoding='utf8')
                third = module.prepare_helper(folder / 'cache')
                self.assertNotEqual(first, third)
                self.assertEqual(len(builds), 2)
                self.assertTrue(first.is_file())
                self.assertTrue(third.is_file())

    def test_prepare_compiler_failure_has_no_partial_executable(self):
        import pointer.windows.composition_host as module
        self.assertTrue(callable(getattr(module, 'prepare_helper', None)), 'Helper compiler missing')
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            source = folder / 'Sidecar.cs'
            source.write_text('helper source', encoding='utf8')
            compiler = folder / 'csc.exe'
            compiler.write_bytes(b'compiler fixture')
            with patch.object(module.sys, 'platform', 'win32'), \
                 patch.object(module, '_compiler_inputs', return_value=(compiler, [source], [])), \
                 patch.object(module.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, b'compile failure', b'')), \
                 self.assertRaisesRegex(OSError, 'compile failure'):
                module.prepare_helper(folder / 'cache')
            self.assertEqual(list((folder / 'cache').glob('*.exe')), [])


class BundledHelperTests(unittest.TestCase):
    def setUp(self):
        import pointer.windows.composition_host as module
        self.module = module

    def make_package(self, root, binary=b'MZ bundled helper fixture'):
        root.mkdir(parents=True, exist_ok=True)
        helper = root / 'native' / 'CompositionSidecar.exe'
        helper.parent.mkdir()
        helper.write_bytes(binary)
        (root / 'Pointer.exe').write_bytes(b'MZ Pointer fixture')
        (root / 'VERSION').write_text('1.3.0-beta.1', encoding='utf8')
        files = {'native/CompositionSidecar.exe': hashlib.sha256(binary).hexdigest(),
                 'Pointer.exe': hashlib.sha256((root / 'Pointer.exe').read_bytes()).hexdigest(),
                 'VERSION': hashlib.sha256((root / 'VERSION').read_bytes()).hexdigest()}
        manifest = dict(version='1.3.0-beta.1', files=files)
        (root / 'PACKAGE.json').write_text(json.dumps(manifest), encoding='utf8')
        return helper, manifest

    def test_bundled_helper_returns_the_manifest_verified_binary(self):
        with tempfile.TemporaryDirectory(prefix='Pointer 发布 路径 ') as directory:
            root = Path(directory)
            helper, _ = self.make_package(root)
            self.assertEqual(self.module.bundled_helper(root), helper.resolve())

    def test_bundled_helper_rejects_missing_or_invalid_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_package(root)
            manifest = root / 'PACKAGE.json'
            manifest.unlink()
            with self.assertRaises(OSError):
                self.module.bundled_helper(root)
            for contents in ('{', '[]', '{"files": []}', '{"files": {}}'):
                with self.subTest(contents=contents):
                    manifest.write_text(contents, encoding='utf8')
                    with self.assertRaises(OSError):
                        self.module.bundled_helper(root)

    def test_bundled_helper_requires_the_exact_manifest_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, manifest = self.make_package(root)
            digest = manifest['files'].pop('native/CompositionSidecar.exe')
            for alias in ('native/../native/CompositionSidecar.exe',
                          'native\\CompositionSidecar.exe'):
                with self.subTest(alias=alias):
                    manifest['files'][alias] = digest
                    (root / 'PACKAGE.json').write_text(json.dumps(manifest), encoding='utf8')
                    with self.assertRaises(OSError):
                        self.module.bundled_helper(root)
                    del manifest['files'][alias]

    def test_bundled_helper_rejects_a_missing_manifested_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper, _ = self.make_package(root)
            helper.unlink()
            with self.assertRaises(OSError):
                self.module.bundled_helper(root)

    def test_bundled_helper_rejects_changed_bytes_even_with_an_mz_header(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper, _ = self.make_package(root)
            helper.write_bytes(b'MZ changed executable fixture')
            with self.assertRaises(OSError):
                self.module.bundled_helper(root)

    def test_bundled_helper_rejects_non_pe_bytes_with_a_matching_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_package(root, b'not a Windows executable')
            with self.assertRaises(OSError):
                self.module.bundled_helper(root)

    def test_bundled_helper_rejects_a_symlink_outside_the_release_root(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            root = folder / 'package'
            helper, _ = self.make_package(root)
            external = folder / 'external-helper.exe'
            external.write_bytes(helper.read_bytes())
            helper.unlink()
            try:
                helper.symlink_to(external)
            except (OSError, NotImplementedError) as error:
                self.skipTest(f'File symlink creation is unavailable: {error}')
            with self.assertRaises(OSError):
                self.module.bundled_helper(root)

    def test_frozen_prepare_uses_bundle_without_compiler_access(self):
        with tempfile.TemporaryDirectory(prefix='Pointer 无编译器 ') as directory:
            root = Path(directory)
            helper, _ = self.make_package(root)
            cache = root / 'unused-client-cache'
            with patch.object(self.module.sys, 'platform', 'win32'), \
                 patch.object(self.module.sys, 'frozen', True, create=True), \
                 patch('pointer.paths.ROOT', root), \
                 patch.object(self.module, '_compiler_inputs', side_effect=OSError('compiler inaccessible')) as inputs, \
                 patch.object(self.module.subprocess, 'run', side_effect=AssertionError('client compilation forbidden')) as compile_process:
                self.assertEqual(self.module.prepare_helper(cache), helper.resolve())
                inputs.assert_not_called()
                compile_process.assert_not_called()
            self.assertFalse(cache.exists())

    def test_frozen_prepare_does_not_fallback_to_cache_when_bundle_is_invalid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            helper, _ = self.make_package(root)
            helper.write_bytes(b'MZ tampered bundled fixture')
            cache = root / 'client-cache'
            cache.mkdir()
            cached = cache / 'CompositionSidecar-cached.exe'
            cached.write_bytes(b'MZ cached executable fixture')
            with patch.object(self.module.sys, 'platform', 'win32'), \
                 patch.object(self.module.sys, 'frozen', True, create=True), \
                 patch('pointer.paths.ROOT', root), \
                 patch.object(self.module, '_compiler_inputs', side_effect=OSError('compiler inaccessible')) as inputs, \
                 patch.object(self.module.subprocess, 'run', side_effect=AssertionError('client compilation forbidden')) as compile_process:
                with self.assertRaises(OSError):
                    self.module.prepare_helper(cache)
                inputs.assert_not_called()
                compile_process.assert_not_called()
            self.assertEqual(cached.read_bytes(), b'MZ cached executable fixture')
