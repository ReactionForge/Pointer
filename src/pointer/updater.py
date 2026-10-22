"""In-App Auto-Update System with SemVer checking, GitHub Releases, and silent installer upgrade."""
import hashlib
from http.client import HTTPResponse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.request
import urllib.error


class UpdateError(Exception):
    """Base error for updater operations."""


class ChecksumMismatchError(UpdateError):
    """Raised when downloaded asset SHA256 does not match expected hash."""


class DownloadError(UpdateError):
    """Raised when downloading installer fails."""


SEMVER_PATTERN = re.compile(r'^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:-([0-9a-zA-Z.-]+))?(?:\+[0-9a-zA-Z.-]+)?$')
MAX_RELEASE_PAGES = 3
RELEASES_PER_PAGE = 30
MAX_RELEASE_METADATA_BYTES = 1024 * 1024


def parse_semver(v_str):
    """Parse semantic version string into comparable tuple: (major, minor, patch, is_prerelease, prerelease_parts).

    Per SemVer 2.0.0: 1.0.0 > 1.0.0-beta.1. Thus is_prerelease = 1 for stable, 0 for prerelease.
    """
    if not isinstance(v_str, str):
        return (0, 0, 0, 0, ())
    v = v_str.strip().lstrip('v').lstrip('V')
    match = SEMVER_PATTERN.fullmatch(v)
    if not match:
        return (0, 0, 0, 0, ())
    major = int(match.group(1))
    minor = int(match.group(2) or 0)
    patch = int(match.group(3) or 0)
    prerelease_str = match.group(4)
    if prerelease_str:
        # Pre-release version has lower precedence than normal version
        parts = []
        for p in prerelease_str.split('.'):
            # Numeric identifiers sort before text and compare numerically.
            parts.append((0, int(p)) if p.isdigit() else (1, p))
        return (major, minor, patch, 0, tuple(parts))
    # Normal release has higher precedence
    return (major, minor, patch, 1, ())


def compare_semver(v1, v2):
    """Compare two version strings. Returns 1 if v1 > v2, 0 if v1 == v2, -1 if v1 < v2."""
    p1, p2 = parse_semver(v1), parse_semver(v2)
    if p1 > p2:
        return 1
    if p1 < p2:
        return -1
    return 0


def is_update_available(latest_str, current_str):
    """Return True if latest_str is strictly newer than current_str."""
    return compare_semver(latest_str, current_str) > 0


def _read_release_metadata(response, deadline):
    if isinstance(response, HTTPResponse):
        chunks, size = [], 0
        while size <= MAX_RELEASE_METADATA_BYTES:
            if time.monotonic() >= deadline:
                raise TimeoutError('检查更新超时')
            chunk = response.read1(min(65536, MAX_RELEASE_METADATA_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
        raw_data = b''.join(chunks)
    else:
        raw_data = response.read(MAX_RELEASE_METADATA_BYTES + 1)
    if len(raw_data) > MAX_RELEASE_METADATA_BYTES:
        raise UpdateError('更新服务响应过大，请稍后重试')
    return json.loads(raw_data.decode('utf-8'))


def check_for_updates(current_version, repo="ReactionForge/Pointer", timeout=8, *, channel=None):
    """Select the highest eligible release within three pages and a time budget.

    A prerelease version follows prereleases and stable releases. A stable
    version follows stable releases. The returned metadata dict is unchanged.
    """
    channel = channel or ('prerelease' if parse_semver(current_version)[4] else 'stable')
    if channel not in ('stable', 'prerelease'):
        raise UpdateError('无效的更新通道')
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 30:
        raise UpdateError('无效的更新检查超时')
    deadline = time.monotonic() + timeout
    selected = None
    try:
        for page in range(1, MAX_RELEASE_PAGES + 1):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('检查更新超时')
            url = f'https://api.github.com/repos/{repo}/releases?per_page={RELEASES_PER_PAGE}&page={page}'
            req = urllib.request.Request(url, headers={
                'User-Agent': f'Pointer-AutoUpdater/{current_version}',
                'Accept': 'application/vnd.github+json',
                'X-GitHub-Api-Version': '2022-11-28',
            })
            with urllib.request.urlopen(req, timeout=remaining) as response:
                releases = _read_release_metadata(response, deadline)
            if time.monotonic() >= deadline:
                raise TimeoutError('检查更新超时')
            if not isinstance(releases, list) or any(not isinstance(item, dict) for item in releases):
                raise UpdateError('更新服务返回了无效发布列表')
            for candidate in releases:
                tag = candidate.get('tag_name', '')
                if candidate.get('draft') or not isinstance(tag, str) or not SEMVER_PATTERN.fullmatch(tag.lstrip('vV')):
                    continue
                if channel == 'stable' and (candidate.get('prerelease') or parse_semver(tag)[4]):
                    continue
                if selected is None or compare_semver(tag, selected['tag_name']) > 0:
                    selected = candidate
            if len(releases) < RELEASES_PER_PAGE:
                break
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as error:
        raise UpdateError(f"检查更新失败：{error}") from error

    data = selected or {'tag_name': current_version}
    tag_name = data.get("tag_name", "")
    latest_version = tag_name.lstrip('v').lstrip('V')
    available = is_update_available(latest_version, current_version)

    # Locate Windows installer asset (.exe)
    assets = data.get("assets", [])
    if not isinstance(assets, list) or any(not isinstance(asset, dict) or not isinstance(asset.get('name'), str) for asset in assets):
        raise UpdateError('更新服务返回了无效安装包列表')
    installer_asset = None

    for asset in assets:
        name = asset.get("name", "").lower()
        if name.endswith(".exe") and ("setup" in name or "installer" in name or "pointer" in name):
            installer_asset = asset

    if not installer_asset and assets:
        for asset in assets:
            if asset.get("name", "").lower().endswith(".exe"):
                installer_asset = asset
                break

    download_url = installer_asset.get("browser_download_url") if installer_asset else None
    asset_name = installer_asset.get("name") if installer_asset else None
    asset_size = installer_asset.get("size", 0) if installer_asset else 0

    # Prefer the selected installer's GitHub digest, then a filename-specific hash.
    expected_sha256 = None
    body_text = data.get("body", "") or ""
    if not isinstance(body_text, str):
        raise UpdateError('更新服务返回了无效更新说明')
    digest = installer_asset.get('digest') if installer_asset else None
    if isinstance(digest, str):
        match = re.fullmatch(r'sha256:([0-9a-fA-F]{64})', digest, re.IGNORECASE)
        if match:
            expected_sha256 = match.group(1).lower()
    if expected_sha256 is None and asset_name:
        name = re.escape(asset_name)
        checksum_line = re.compile(
            rf'(?:([0-9a-f]{{64}})\s+\*?{name}'
            rf'|{name}\s*(?:\||:|=)?\s*(?:sha-?256\s*[:=]?\s*)?([0-9a-f]{{64}})'
            rf'|sha-?256\s*\({name}\)\s*=\s*([0-9a-f]{{64}}))', re.IGNORECASE)
        hashes = set()
        for line in body_text.splitlines():
            match = checksum_line.fullmatch(line.replace('`', '').strip().strip('|').strip())
            if match:
                hashes.add(next(value for value in match.groups() if value).lower())
        if len(hashes) == 1:
            expected_sha256 = hashes.pop()
    can_auto_install = bool(
        available and isinstance(download_url, str) and download_url.startswith('https://')
        and asset_name and Path(asset_name).name == asset_name
        and type(asset_size) is int and asset_size > 0 and expected_sha256)

    return {
        "available": available,
        "current_version": current_version,
        "latest_version": latest_version,
        "tag_name": tag_name,
        "release_name": data.get("name") or tag_name,
        "published_at": (data.get("published_at") or "")[:10],
        "release_notes": body_text,
        "download_url": download_url,
        "asset_name": asset_name,
        "asset_size": asset_size,
        "expected_sha256": expected_sha256,
        "can_auto_install": can_auto_install,
        "html_url": data.get("html_url", f"https://github.com/{repo}/releases"),
    }


def _package_metadata(expected_sha256, expected_size, *, required=False):
    if expected_sha256 is not None and (
            not isinstance(expected_sha256, str) or
            re.fullmatch(r'[0-9a-fA-F]{64}', expected_sha256) is None):
        raise UpdateError('安装包 SHA-256 无效')
    if expected_size is not None and (type(expected_size) is not int or expected_size <= 0):
        raise UpdateError('安装包长度无效')
    if required and (expected_sha256 is None or expected_size is None):
        raise UpdateError('自动安装需要此安装包的 SHA-256 和长度')
    return expected_sha256.lower() if expected_sha256 is not None else None


def download_update_package(url, destination_path, expected_sha256=None, progress_callback=None,
                            cancel_flag=None, *, expected_size=None):
    """Validate a private temporary download before replacing the destination.

    Manual downloads may omit metadata; automatic installation requires both
    fields again at launch. HTTP Content-Length is checked in either mode.
    """
    expected_sha256 = _package_metadata(expected_sha256, expected_size)
    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    hasher = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": "Pointer-Update-Downloader"})

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            header = response.headers.get('Content-Length')
            content_length = None
            if header is not None:
                if not re.fullmatch(r'[0-9]+', str(header)):
                    raise DownloadError('下载响应长度无效')
                content_length = int(header)
            if expected_size is not None and content_length is not None and expected_size != content_length:
                raise DownloadError('下载响应长度与安装包长度不符')
            total_size = expected_size if expected_size is not None else content_length
            downloaded = 0
            with tempfile.NamedTemporaryFile(mode='wb', dir=destination.parent,
                                             prefix=destination.name + '.', suffix='.download.tmp',
                                             delete=False) as out_file:
                temp_path = Path(out_file.name)
                while True:
                    if cancel_flag and cancel_flag():
                        raise DownloadError('下载已由用户取消')
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if total_size is not None and downloaded > total_size:
                        raise DownloadError('下载数据超出安装包长度')
                    out_file.write(chunk)
                    hasher.update(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size or 0)
            if not downloaded or (total_size is not None and downloaded != total_size):
                raise DownloadError('下载不完整，安装包长度不符')

        computed_sha256 = hasher.hexdigest()
        if expected_sha256 is not None and computed_sha256 != expected_sha256:
            raise ChecksumMismatchError('安装包 SHA-256 校验失败')
        if cancel_flag and cancel_flag():
            raise DownloadError('下载已由用户取消')
        os.replace(temp_path, destination)
        return computed_sha256
    except Exception as error:
        if isinstance(error, UpdateError):
            raise
        raise DownloadError(f'下载失败：{error}') from error
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _open_locked_installer(installer):
    """Keep the verified Windows file immutable until CreateProcess returns."""
    if os.name != 'nt':
        raise UpdateError('自动安装仅支持 Windows')
    import ctypes
    from ctypes import wintypes
    import msvcrt
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create_file = kernel.CreateFileW
    create_file.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                            wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create_file.restype = wintypes.HANDLE
    close_handle = kernel.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    # FILE_SHARE_READ permits the loader's read/execute access, but denies both
    # in-place writes and path replacement while this verification handle lives.
    handle = create_file(str(installer), 0x80000000, 0x1, None, 3, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
    except BaseException:
        close_handle(handle)
        raise
    try:
        return os.fdopen(descriptor, 'rb')
    except BaseException:
        os.close(descriptor)
        raise


def trigger_silent_upgrade(installer_path, application=None, *, expected_sha256=None, expected_size=None):
    """Verify and launch the installer; only the installer may stop the runtime.

    ``application`` remains accepted for callers of the previous API. It is
    deliberately unused so a failed launch cannot change runtime state.
    """
    expected_sha256 = _package_metadata(expected_sha256, expected_size, required=True)
    installer = Path(installer_path).resolve()
    if not installer.is_file():
        raise FileNotFoundError(f'升级安装包不存在：{installer}')
    hasher = hashlib.sha256()
    size = 0
    with _open_locked_installer(installer) as source:
        while chunk := source.read(65536):
            size += len(chunk)
            if size > expected_size:
                raise DownloadError('安装包长度不符')
            hasher.update(chunk)
        if size != expected_size:
            raise DownloadError('安装包长度不符')
        if hasher.hexdigest() != expected_sha256:
            raise ChecksumMismatchError('安装包 SHA-256 校验失败')

        return subprocess.Popen(
            [str(installer), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART'],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,  # CREATE_NO_WINDOW
        )
