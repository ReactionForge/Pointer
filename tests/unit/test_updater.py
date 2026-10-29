"""Unit tests for SemVer parsing, update checking, and updater workflow."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from pointer.updater import (
    parse_semver,
    compare_semver,
    is_update_available,
    check_for_updates,
    download_update_package,
    trigger_silent_upgrade,
    ChecksumMismatchError,
    DownloadError,
    UpdateError,
)


class UpdaterTests(unittest.TestCase):
    def test_semver_parsing_and_precedence(self):
        # Normal version vs prerelease
        self.assertEqual(compare_semver("1.3.0", "1.3.0-beta.1"), 1)
        self.assertEqual(compare_semver("1.3.0-beta.1", "1.3.0"), -1)
        self.assertEqual(compare_semver("1.3.0-beta.2", "1.3.0-beta.1"), 1)
        self.assertEqual(compare_semver("1.4.0", "1.3.9"), 1)
        self.assertEqual(compare_semver("2.0.0", "1.99.99"), 1)
        self.assertEqual(compare_semver("v1.3.0", "1.3.0"), 0)
        self.assertEqual(compare_semver("1.3.0", "1.3.0"), 0)

    def test_is_update_available(self):
        self.assertTrue(is_update_available("1.3.1", "1.3.0-beta.1"))
        self.assertTrue(is_update_available("1.3.0", "1.3.0-beta.1"))
        self.assertFalse(is_update_available("1.3.0-beta.1", "1.3.0"))
        self.assertFalse(is_update_available("1.3.0", "1.3.0"))

    def test_check_for_updates_parses_release_and_assets(self):
        fake_response = {
            "tag_name": "v1.4.0",
            "name": "Pointer v1.4.0 全新版本",
            "published_at": "2026-10-04T12:00:00Z",
            "body": "## 更新日志\n- 支持 8 款设计师调色\n0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef  Pointer-v1.4.0-setup-x64.exe",
            "assets": [
                {
                    "name": "Pointer-v1.4.0-setup-x64.exe",
                    "browser_download_url": "https://github.com/ReactionForge/Pointer/releases/download/v1.4.0/Pointer-v1.4.0-setup-x64.exe",
                    "size": 15000000,
                }
            ],
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps([fake_response]).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            info = check_for_updates("1.3.0-beta.1")
            self.assertTrue(info["available"])
            self.assertEqual(info["latest_version"], "1.4.0")
            self.assertEqual(info["asset_name"], "Pointer-v1.4.0-setup-x64.exe")
            self.assertEqual(info["expected_sha256"], "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")

    def test_download_and_verify_sha256(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "installer.exe"
            data = b"Simulated installer content for testing"
            expected_hash = hashlib.sha256(data).hexdigest()

            mock_resp = MagicMock()
            mock_resp.headers = {"Content-Length": str(len(data))}
            mock_resp.read.side_effect = [data, b""]
            mock_resp.__enter__.return_value = mock_resp

            progress_calls = []
            def on_progress(done, total):
                progress_calls.append((done, total))

            with patch("urllib.request.urlopen", return_value=mock_resp):
                computed = download_update_package(
                    "https://example.com/installer.exe",
                    dest,
                    expected_sha256=expected_hash,
                    progress_callback=on_progress,
                )
                self.assertEqual(computed, expected_hash)
                self.assertTrue(dest.exists())
                self.assertEqual(dest.read_bytes(), data)
                self.assertEqual(progress_calls[-1], (len(data), len(data)))

    def test_download_checksum_mismatch_raises_and_cleans_up(self):
        with tempfile.TemporaryDirectory() as folder:
            dest = Path(folder) / "installer.exe"
            data = b"Corrupted content"

            mock_resp = MagicMock()
            mock_resp.headers = {"Content-Length": str(len(data))}
            mock_resp.read.side_effect = [data, b""]
            mock_resp.__enter__.return_value = mock_resp

            with patch("urllib.request.urlopen", return_value=mock_resp):
                with self.assertRaises(ChecksumMismatchError):
                    download_update_package(
                        "https://example.com/installer.exe",
                        dest,
                        expected_sha256="deadbeef" * 8,
                    )
                self.assertFalse(dest.exists())

    def test_trigger_silent_upgrade(self):
        with tempfile.TemporaryDirectory() as folder:
            fake_exe = Path(folder) / "installer.exe"
            fake_exe.write_bytes(b"exe")

            app_mock = MagicMock()
            with patch("subprocess.Popen") as mock_popen:
                trigger_silent_upgrade(fake_exe, application=app_mock,
                                       expected_sha256=hashlib.sha256(b'exe').hexdigest(), expected_size=3)
                app_mock.prepare_upgrade.assert_not_called()
                mock_popen.assert_called_once()
                args, kwargs = mock_popen.call_args
                self.assertIn("/VERYSILENT", args[0])
                self.assertIn("/SUPPRESSMSGBOXES", args[0])
                self.assertIn("/NORESTART", args[0])


class PackageIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.target = Path(self.folder.name) / 'setup.exe'
        self.target.write_bytes(b'previous verified installer')
        self.content = b'new installer'
        self.digest = hashlib.sha256(self.content).hexdigest()

    def response(self, *, length=None, chunks=None):
        result = MagicMock()
        result.__enter__.return_value = result
        result.headers = {} if length is None else {'Content-Length': str(length)}
        result.read.side_effect = chunks if chunks is not None else [self.content, b'']
        return result

    def assert_preserved(self):
        self.assertEqual(self.target.read_bytes(), b'previous verified installer')
        self.assertEqual(list(self.target.parent.iterdir()), [self.target])

    def test_truncated_download_keeps_verified_destination(self):
        response = self.response(length=len(self.content), chunks=[self.content[:-1], b''])
        with patch('urllib.request.urlopen', return_value=response), self.assertRaises(DownloadError):
            download_update_package('https://example.com/setup.exe', self.target,
                                    expected_sha256=self.digest, expected_size=len(self.content))
        self.assert_preserved()

    def test_extra_bytes_are_rejected_without_metadata_as_well(self):
        response = self.response(length=len(self.content) - 1)
        with patch('urllib.request.urlopen', return_value=response), self.assertRaises(DownloadError):
            download_update_package('https://example.com/setup.exe', self.target)
        self.assert_preserved()

    def test_asset_length_mismatch_rejects_headers_before_reading_body(self):
        response = self.response(length=len(self.content) + 1)
        with patch('urllib.request.urlopen', return_value=response), self.assertRaises(DownloadError):
            download_update_package('https://example.com/setup.exe', self.target,
                                    expected_sha256=self.digest, expected_size=len(self.content))
        response.read.assert_not_called()
        self.assert_preserved()

    def test_missing_header_still_checks_selected_asset_length(self):
        response = self.response(chunks=[self.content[:-1], b''])
        with patch('urllib.request.urlopen', return_value=response), self.assertRaises(DownloadError):
            download_update_package('https://example.com/setup.exe', self.target,
                                    expected_size=len(self.content))
        self.assert_preserved()

    def test_bad_digest_keeps_verified_destination(self):
        with patch('urllib.request.urlopen', return_value=self.response()), self.assertRaises(ChecksumMismatchError):
            download_update_package('https://example.com/setup.exe', self.target,
                                    expected_sha256='0' * 64, expected_size=len(self.content))
        self.assert_preserved()

    def test_network_failure_after_partial_data_keeps_verified_destination(self):
        response = self.response(chunks=[self.content[:3], OSError('connection reset')])
        with patch('urllib.request.urlopen', return_value=response), self.assertRaisesRegex(DownloadError, 'connection reset'):
            download_update_package('https://example.com/setup.exe', self.target,
                                    expected_sha256=self.digest, expected_size=len(self.content))
        self.assert_preserved()

    def test_failed_atomic_replace_does_not_unlink_verified_destination(self):
        with patch('urllib.request.urlopen', return_value=self.response()), \
                patch('pointer.updater.os.replace', side_effect=PermissionError('locked')), \
                self.assertRaisesRegex(DownloadError, 'locked'):
            download_update_package('https://example.com/setup.exe', self.target,
                                    expected_sha256=self.digest, expected_size=len(self.content))
        self.assert_preserved()

    def test_cancel_after_last_read_preserves_existing_installer(self):
        cancelled = MagicMock(side_effect=[False, False, True])
        with patch('urllib.request.urlopen', return_value=self.response()), self.assertRaisesRegex(DownloadError, '取消'):
            download_update_package('https://example.com/setup.exe', self.target,
                                    expected_sha256=self.digest, expected_size=len(self.content), cancel_flag=cancelled)
        self.assert_preserved()

    def test_manual_download_without_digest_and_header_remains_supported(self):
        with patch('urllib.request.urlopen', return_value=self.response()):
            digest = download_update_package('https://example.com/setup.exe', self.target)
        self.assertEqual(digest, self.digest)
        self.assertEqual(self.target.read_bytes(), self.content)
        self.assertEqual(list(self.target.parent.iterdir()), [self.target])

    def test_malformed_metadata_fails_before_network_or_destination_change(self):
        for metadata in ({'expected_sha256': 'broken'}, {'expected_size': -1}, {'expected_size': True}):
            with self.subTest(metadata=metadata), patch('urllib.request.urlopen') as request:
                with self.assertRaises(UpdateError):
                    download_update_package('https://example.com/setup.exe', self.target, **metadata)
                request.assert_not_called()
                self.assert_preserved()

    def test_launch_failure_leaves_runtime_and_preferences_untouched(self):
        self.target.write_bytes(self.content)
        application = MagicMock()
        with patch('subprocess.Popen', side_effect=OSError('cannot spawn')), self.assertRaisesRegex(OSError, 'cannot spawn'):
            trigger_silent_upgrade(self.target, application, expected_sha256=self.digest, expected_size=len(self.content))
        self.assertEqual(application.mock_calls, [])

    def test_launch_revalidates_changed_bytes_and_length_without_side_effects(self):
        application = MagicMock()
        for content in (b'x' * len(self.content), self.content[:-1], self.content + b'x'):
            with self.subTest(content=content), patch('subprocess.Popen') as start:
                self.target.write_bytes(content)
                with self.assertRaises(UpdateError):
                    trigger_silent_upgrade(self.target, application, expected_sha256=self.digest, expected_size=len(self.content))
                start.assert_not_called()
                self.assertEqual(application.mock_calls, [])


@unittest.skipUnless(os.name == 'nt', 'Windows file-sharing semantics')
class InstallerFileLockTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.target = Path(self.folder.name)/'setup.exe'
        self.original = b'verified installer A'
        self.changed = b'replaced installer B'
        self.assertEqual(len(self.original), len(self.changed))
        self.target.write_bytes(self.original)
        self.digest = hashlib.sha256(self.original).hexdigest()
        self.application = MagicMock()

    def launch(self, **overrides):
        metadata = {'expected_sha256': self.digest, 'expected_size': len(self.original)}
        metadata.update(overrides)
        return trigger_silent_upgrade(self.target, self.application, **metadata)

    def test_verified_file_cannot_be_written_or_replaced_until_popen_returns(self):
        replacement = self.target.with_name('replacement.exe')
        replacement.write_bytes(self.changed)
        process = MagicMock()
        def create_process(command, **kwargs):
            self.assertTrue(os.path.samefile(command[0], self.target))
            with self.assertRaises(PermissionError):
                self.target.write_bytes(self.changed)
            with self.assertRaises(PermissionError):
                os.replace(replacement, self.target)
            self.assertEqual(self.target.read_bytes(), self.original)
            return process
        with patch('subprocess.Popen', side_effect=create_process) as start:
            self.assertIs(self.launch(), process)
        start.assert_called_once()
        self.assertEqual(self.application.mock_calls, [])
        # The caller can replace it again only after CreateProcess has returned.
        os.replace(replacement, self.target)
        self.assertEqual(self.target.read_bytes(), self.changed)

    def test_open_writer_prevents_verification_and_process_creation(self):
        with self.target.open('r+b'), patch('subprocess.Popen') as start:
            with self.assertRaises(PermissionError):
                self.launch()
        start.assert_not_called()
        self.assertEqual(self.application.mock_calls, [])

    def test_process_creation_failure_releases_lock(self):
        with patch('subprocess.Popen', side_effect=OSError('cannot spawn')):
            with self.assertRaisesRegex(OSError, 'cannot spawn'):
                self.launch()
        self.target.write_bytes(self.changed)
        self.assertEqual(self.target.read_bytes(), self.changed)
        self.assertEqual(self.application.mock_calls, [])

    def test_verification_failures_release_lock_without_launching(self):
        for metadata in ({'expected_sha256': '0'*64}, {'expected_size': len(self.original) - 1},
                         {'expected_size': len(self.original) + 1}):
            with self.subTest(metadata=metadata), patch('subprocess.Popen') as start:
                self.target.write_bytes(self.original)
                with self.assertRaises(UpdateError):
                    self.launch(**metadata)
                start.assert_not_called()
                self.target.write_bytes(self.changed)
                self.assertEqual(self.target.read_bytes(), self.changed)
        self.assertEqual(self.application.mock_calls, [])

    def test_failed_descriptor_conversion_closes_native_handle(self):
        with patch('msvcrt.open_osfhandle', side_effect=OSError('descriptor failed')), \
                patch('subprocess.Popen') as start:
            with self.assertRaisesRegex(OSError, 'descriptor failed'):
                self.launch()
        start.assert_not_called()
        self.target.write_bytes(self.changed)

    def test_failed_file_wrapper_closes_descriptor(self):
        with patch('pointer.updater.os.fdopen', side_effect=OSError('wrapper failed')), \
                patch('subprocess.Popen') as start:
            with self.assertRaisesRegex(OSError, 'wrapper failed'):
                self.launch()
        start.assert_not_called()
        self.target.write_bytes(self.changed)


if __name__ == "__main__":
    unittest.main()
