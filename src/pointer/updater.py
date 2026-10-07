"""In-App Auto-Update System with SemVer checking, GitHub Releases, and silent installer upgrade."""
import hashlib
from http.client import HTTPResponse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
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
        for line in body_text.splitlines():
            match = re.search(r'\b([0-9a-fA-F]{64})\b', line)
            if asset_name in line and match:
                expected_sha256 = match.group(1).lower()
                break
    if expected_sha256 is None:
        hashes = re.findall(r'\b([0-9a-fA-F]{64})\b', body_text)
        named_checksum = any(re.search(r'\b[0-9a-fA-F]{64}\b', line) and
                             re.search(r'\.(?:zip|exe)\b', line, re.IGNORECASE)
                             for line in body_text.splitlines())
        if len(hashes) == 1 and not named_checksum:
            expected_sha256 = hashes[0].lower()

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
        "html_url": data.get("html_url", f"https://github.com/{repo}/releases"),
    }


def download_update_package(url, destination_path, expected_sha256=None, progress_callback=None, cancel_flag=None):
    """Download update package with progress reporting, atomic write, and SHA256 verification."""
    destination = Path(destination_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp_path = destination.with_suffix(".download.tmp")

    hasher = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": "Pointer-Update-Downloader"})

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            total_size = int(response.headers.get("Content-Length", 0))
            downloaded = 0
            with open(temp_path, "wb") as out_file:
                while True:
                    if cancel_flag and cancel_flag():
                        raise DownloadError("下载已由用户取消")
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    hasher.update(chunk)
                    downloaded += len(chunk)
                    if progress_callback:
                        progress_callback(downloaded, total_size)

        computed_sha256 = hasher.hexdigest().lower()
        if expected_sha256 and computed_sha256 != expected_sha256.lower():
            temp_path.unlink(missing_ok=True)
            raise ChecksumMismatchError(
                f"安装包校验失败！期望值：{expected_sha256[:16]}...，计算值：{computed_sha256[:16]}..."
            )

        if destination.exists():
            destination.unlink(missing_ok=True)
        os.replace(temp_path, destination)
        return computed_sha256
    except Exception as error:
        temp_path.unlink(missing_ok=True)
        if isinstance(error, UpdateError):
            raise
        raise DownloadError(f"下载失败：{error}") from error


def trigger_silent_upgrade(installer_path, application=None):
    """Call prepare_gui_upgrade to shut down UI gracefully, then invoke installer in silent mode."""
    installer = Path(installer_path).resolve()
    if not installer.is_file():
        raise FileNotFoundError(f"升级安装包不存在：{installer}")

    if application is not None:
        application.prepare_upgrade()

    # Launch Inno Setup installer silently
    # /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
    cmd = [
        str(installer),
        "/VERYSILENT",
        "/SUPPRESSMSGBOXES",
        "/NORESTART",
    ]
    # Detach process so it outlives caller
    creation_flags = 0x08000000  # CREATE_NO_WINDOW
    subprocess.Popen(
        cmd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation_flags,
    )
