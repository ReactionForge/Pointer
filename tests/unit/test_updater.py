"""Unit tests for SemVer parsing, update checking, and updater workflow."""
import hashlib
import json
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
            "body": "## 更新日志\n- 支持 8 款设计师调色\n- SHA256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "assets": [
                {
                    "name": "Pointer-v1.4.0-setup-x64.exe",
                    "browser_download_url": "https://github.com/ReactionForge/Pointer/releases/download/v1.4.0/Pointer-v1.4.0-setup-x64.exe",
                    "size": 15000000,
                }
            ],
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(fake_response).encode("utf-8")
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
                trigger_silent_upgrade(fake_exe, application=app_mock)
                app_mock.prepare_upgrade.assert_called_once()
                mock_popen.assert_called_once()
                args, kwargs = mock_popen.call_args
                self.assertIn("/VERYSILENT", args[0])
                self.assertIn("/SUPPRESSMSGBOXES", args[0])
                self.assertIn("/NORESTART", args[0])


if __name__ == "__main__":
    unittest.main()
