"""Release channels, bounded network responses and SemVer update eligibility."""
import json
import time
from pathlib import Path
import tempfile
import unittest
from http.client import HTTPResponse
from unittest.mock import MagicMock, patch

from pointer.updater import check_for_updates, compare_semver, trigger_silent_upgrade, UpdateError


def release(version, *, draft=False, prerelease=False, assets=None):
    return {'tag_name': f'v{version}', 'draft': draft, 'prerelease': prerelease,
            'assets': assets or [], 'body': '', 'published_at': '2026-10-07T00:00:00Z'}


def response(payload):
    result = MagicMock()
    result.__enter__.return_value = result
    result.read.return_value = json.dumps(payload).encode('utf-8')
    result.headers = {}
    return result


class UpdaterBoundaryTests(unittest.TestCase):
    def test_semver_numeric_identifiers_build_metadata_and_release_order(self):
        versions = ['1.0.0-alpha', '1.0.0-alpha.1', '1.0.0-alpha.beta', '1.0.0-beta',
                    '1.0.0-beta.2', '1.0.0-beta.11', '1.0.0-rc.1', '1.0.0']
        for older, newer in zip(versions, versions[1:]):
            with self.subTest(older=older, newer=newer):
                self.assertLess(compare_semver(older, newer), 0)
        self.assertEqual(compare_semver('1.3.0-beta.4+build.7', '1.3.0-beta.4+build.9'), 0)
        self.assertGreater(compare_semver('1.3.0-beta.4+build.7', '1.3.0-beta.3'), 0)

    def test_beta_channel_discovers_next_beta_and_later_stable_ignoring_drafts(self):
        for extra, expected in (([], '1.3.0-beta.4'), ([release('1.3.0')], '1.3.0')):
            with self.subTest(expected=expected):
                releases = [release('9.0.0', draft=True), release('1.3.0-beta.4', prerelease=True),
                            release('1.1.1'), release('1.3.0-beta.3', prerelease=True)] + extra
                with patch('urllib.request.urlopen', return_value=response(releases)) as request:
                    info = check_for_updates('1.3.0-beta.3')
                self.assertTrue(info['available'])
                self.assertEqual(info['latest_version'], expected)
                self.assertIn('/releases?', request.call_args.args[0].full_url)

    def test_stable_channel_excludes_prereleases_even_if_api_flags_are_wrong(self):
        releases = [release('1.5.0-beta.1'), release('1.4.0'),
                    release('1.6.0', prerelease=True), release('2.0.0', draft=True)]
        with patch('urllib.request.urlopen', return_value=response(releases)):
            info = check_for_updates('1.3.0')
        self.assertEqual(info['latest_version'], '1.4.0')
        self.assertTrue(info['available'])
        with patch('urllib.request.urlopen', return_value=response([release('1.4.0-beta.1', prerelease=True)])):
            self.assertFalse(check_for_updates('1.3.0')['available'])

    def test_pagination_is_bounded_and_newer_eligible_version_can_be_on_second_page(self):
        page = [release(f'0.0.{i}', draft=True) for i in range(30)]
        with patch('urllib.request.urlopen', side_effect=[response(page), response([release('1.3.0-beta.4', prerelease=True)])]) as request:
            self.assertEqual(check_for_updates('1.3.0-beta.3')['latest_version'], '1.3.0-beta.4')
        self.assertEqual(request.call_count, 2)
        self.assertIn('page=2', request.call_args.args[0].full_url)
        with patch('urllib.request.urlopen', return_value=response(page)) as request:
            self.assertFalse(check_for_updates('1.3.0-beta.3')['available'])
        self.assertEqual(request.call_count, 3)

    def test_invalid_or_oversize_metadata_fails_with_a_user_facing_error(self):
        for payload in ({'unexpected': 'object'}, [None], [dict(release('1.4.0'), assets=['invalid'])]):
            with self.subTest(payload=payload), patch('urllib.request.urlopen', return_value=response(payload)):
                with self.assertRaises(UpdateError):
                    check_for_updates('1.3.0')
        oversized = response([])
        oversized.read.return_value = b' ' * (1024 * 1024 + 1)
        with patch('urllib.request.urlopen', return_value=oversized), self.assertRaises(UpdateError):
            check_for_updates('1.3.0')
        self.assertTrue(oversized.read.call_args.args, 'Metadata read must have a byte limit')

    def test_connection_failure_and_expired_total_budget_stop_the_check(self):
        with patch('urllib.request.urlopen', side_effect=TimeoutError('timed out')), self.assertRaises(UpdateError):
            check_for_updates('1.3.0')
        page = [release(f'0.0.{i}', draft=True) for i in range(30)]
        clock = iter([0, 0, 9])
        with patch('urllib.request.urlopen', return_value=response(page)) as request, \
                patch('time.monotonic', side_effect=lambda: next(clock, 9)):
            with self.assertRaises(UpdateError):
                check_for_updates('1.3.0', timeout=8)
        self.assertEqual(request.call_count, 1, 'A second request must not start after the budget expires')

    def test_checksum_belongs_to_the_selected_installer_not_the_archive(self):
        installer_hash, zip_hash = 'a' * 64, 'b' * 64
        installer = {'name': 'Pointer-v1.4.0-setup-x64.exe', 'browser_download_url': 'https://invalid.example/setup.exe'}
        bodies = [(f'ZIP SHA256: {zip_hash}', f'sha256:{installer_hash}', installer_hash),
                  (f'{zip_hash}  Pointer-v1.4.0-windows-x64.zip\n{installer_hash}  {installer["name"]}', None, installer_hash),
                  (f'{zip_hash}  Pointer-v1.4.0-windows-x64.zip', None, None),
                  (f'Archive: {zip_hash}\nOther: {installer_hash}', None, None)]
        for body, digest, expected in bodies:
            with self.subTest(digest=digest, expected=expected):
                metadata = dict(release('1.4.0', assets=[dict(installer, digest=digest)]), body=body)
                with patch('urllib.request.urlopen', return_value=response([metadata])):
                    self.assertEqual(check_for_updates('1.3.0')['expected_sha256'], expected)

    def test_unverified_package_cannot_prepare_or_launch_installer(self):
        with tempfile.TemporaryDirectory() as folder:
            installer = Path(folder) / 'setup.exe'
            installer.write_bytes(b'fake installer')
            application = MagicMock()
            with patch('subprocess.Popen') as start:
                with self.assertRaisesRegex(UpdateError, 'SHA-256'):
                    trigger_silent_upgrade(installer, application)
                start.assert_not_called()
                application.prepare_upgrade.assert_not_called()

    def test_unbound_ambiguous_or_similar_filename_checksums_do_not_enable_install(self):
        name, digest = 'Pointer-setup.exe', 'a' * 64
        installer = {'name': name, 'browser_download_url': 'https://invalid.example/setup.exe', 'size': 3}
        for body in (f'SHA256: {digest}', f'{digest}  old-{name}', f'{digest}  {name}.zip',
                     f'{digest}  {name}\n' + 'b' * 64 + f'  {name}'):
            with self.subTest(body=body):
                metadata = dict(release('1.4.0', assets=[installer]), body=body)
                with patch('urllib.request.urlopen', return_value=response([metadata])):
                    info = check_for_updates('1.3.0')
                self.assertIsNone(info['expected_sha256'])
                self.assertFalse(info['can_auto_install'])
                self.assertEqual(info['download_url'], installer['browser_download_url'])

    def test_auto_install_requires_a_positive_integer_asset_size(self):
        for size in (None, 0, -1, True, '3', 3):
            with self.subTest(size=size):
                asset = {'name': 'Pointer-setup.exe', 'browser_download_url': 'https://invalid.example/setup.exe',
                         'digest': 'sha256:' + 'a' * 64, 'size': size}
                with patch('urllib.request.urlopen', return_value=response([release('1.4.0', assets=[asset])])):
                    info = check_for_updates('1.3.0')
                self.assertEqual(info['can_auto_install'], type(size) is int and size > 0)


if __name__ == '__main__':
    unittest.main()
