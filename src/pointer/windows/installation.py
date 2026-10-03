"""Verified package installation, migration and owned-file cleanup."""
import base64, hashlib, json, os, shutil, subprocess, time
from pathlib import Path, PurePosixPath
from pointer.paths import ROOT, DATA_ROOT, INSTALL_ROOT, FROZEN
from . import scheme as config, engine as switcher

def package_files(root):
    """Validate a release manifest before copying files to the installation."""
    value = json.loads((root / "PACKAGE.json").read_text(encoding="utf-8"))
    if value.get("version") != (root / "VERSION").read_text(encoding="utf-8").strip():
        raise ValueError("Package version does not match VERSION")
    files = value.get("files")
    if not isinstance(files, dict) or "Pointer.exe" not in files:
        raise ValueError("Package manifest is incomplete")
    for name, digest in files.items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts or ":" in name or "\\" in name:
            raise ValueError(f"Invalid package path: {name}")
        path = root.joinpath(*relative.parts).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            raise ValueError(f"Missing package file: {name}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError(f"Package checksum mismatch: {name}")
    return files


def _previous_directory():
    arrow = config.read_values(config.KEY_PATH).get("Arrow", {}).get("value", "")
    path = Path(os.path.expandvars(arrow)) if isinstance(arrow, str) and arrow else None
    if not path:
        return None
    if path.name == "adaptive-arrow.cur" and path.parent.name in ("light", "dark"):
        if path.parent.parent.name == "dual-contrast":
            root = path.parent.parent.parent
        elif (path.parent.parent.name == "adaptive" and path.parents[2].name == "cursors"
              and path.parents[3].name == "assets"):
            root = path.parents[4]
        else:
            return None
    elif path.name in ("reference-black-arrow.cur", "adaptive-arrow.cur"):
        if path.parent.name == "reference" and path.parents[1].name == "cursors":
            root = path.parents[3]
        else:
            root = path.parent.parent if path.parent.name == "adaptive" else path.parent
    else:
        return None
    root = root.resolve()
    if ((root / "configure_cursor.py").is_file() or (root / "Pointer.exe").is_file()
            or (root / "src" / "pointer" / "configure_cursor.py").is_file()):
        return root
    return None


def _migrate_backup(previous):
    """Copy only this user's backup; downloaded packages never contain one."""
    if config.BACKUP.exists():
        config.validate_backup(json.loads(config.BACKUP.read_text(encoding="utf-8")))
        return
    if not previous:
        return
    previous_data = previous / ".local" / "data"
    if not previous_data.is_dir():
        previous_data = previous.parent / "data" if (previous / "Pointer.exe").is_file() else previous
    old_backup = previous_data / config.BACKUP.name
    if old_backup.is_file():
        config.save_backup(config.validate_backup(json.loads(old_backup.read_text(encoding="utf-8"))))
    old_startup = previous_data / switcher.STARTUP_BACKUP.name
    if old_startup.is_file() and not switcher.STARTUP_BACKUP.exists():
        data = json.loads(old_startup.read_text(encoding="utf-8"))
        if data.get("value_name") != switcher.RUN_VALUE or not isinstance(data.get("installed_command"), str):
            raise ValueError("Invalid startup backup")
        switcher._atomic_json(switcher.STARTUP_BACKUP, data)


def _shortcuts():
    menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Pointer"
    menu.mkdir(parents=True, exist_ok=True)
    executable = INSTALL_ROOT.resolve() / "Pointer.exe"
    pairs = [("启用自适应光标", "--apply"), ("停止自动切换", "--stop"),
             ("恢复原光标", "--restore"), ("打开测试页", "--test-page"),
             ("使用倾斜动效", "--tilt"), ("使用缩小回弹", "--shrink")]
    def literal(value):
        return "'" + str(value).replace("'", "''") + "'"
    commands = ["$pointerShell = New-Object -ComObject WScript.Shell"]
    for title, arguments in pairs:
        commands.extend([f"$pointerShortcut = $pointerShell.CreateShortcut({literal(menu / (title + '.lnk'))})",
                         f"$pointerShortcut.TargetPath = {literal(executable)}",
                         f"$pointerShortcut.Arguments = {literal(arguments)}",
                         f"$pointerShortcut.WorkingDirectory = {literal(INSTALL_ROOT.resolve())}",
                         "$pointerShortcut.Save()"])
    encoded = base64.b64encode("\n".join(commands).encode("utf-16-le")).decode("ascii")
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                   check=True, creationflags=0x08000000, capture_output=True)


def remove_obsolete_files(previous_files, current_files, directory):
    """Remove verified files owned by the old release, preserving user additions."""
    directory = directory.resolve()
    parents = set()
    for name, digest in previous_files.items():
        if name in current_files:
            continue
        path = (directory / name).resolve()
        if not path.is_relative_to(directory) or not path.is_file():
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            continue
        path.unlink()
        parents.update(parent for parent in path.parents if parent != directory and parent.is_relative_to(directory))
    for parent in sorted(parents, key=lambda value: len(value.parts), reverse=True):
        try:
            parent.rmdir()
        except OSError:
            pass


def install():
    if not FROZEN:
        raise ValueError("源码模式请使用 --apply；一键安装请运行发布包中的 Pointer.exe。")
    files = package_files(ROOT)
    previous_files = {}
    if ROOT.resolve() != INSTALL_ROOT.resolve() and (INSTALL_ROOT / "PACKAGE.json").is_file():
        try:
            previous_files = package_files(INSTALL_ROOT)
        except (ValueError, FileNotFoundError):
            # Modified files are not safe candidates for automatic cleanup.
            pass
    previous = _previous_directory()
    _migrate_backup(previous)
    if previous:
        switcher.stop_directory(previous)
    switcher.stop_directory(INSTALL_ROOT)
    if ROOT.resolve() != INSTALL_ROOT.resolve():
        INSTALL_ROOT.mkdir(parents=True, exist_ok=True)
        for name in [*files, "PACKAGE.json"]:
            source = ROOT / name
            target = INSTALL_ROOT / name
            target.parent.mkdir(parents=True, exist_ok=True)
            deadline = time.monotonic() + 4
            while True:
                try:
                    shutil.copy2(source, target)
                    break
                except PermissionError as error:
                    # The stopped helper can release its mutex just before Windows
                    # unloads its DLLs. Allow that shutdown to finish before updating.
                    if getattr(error, "winerror", None) not in (32, 33) or time.monotonic() >= deadline:
                        raise RuntimeError(f"无法更新 {name}，请关闭该程序后重试：{error}") from error
                    time.sleep(.1)
        _shortcuts()
        report = DATA_ROOT / "install-apply-report.json"
        environment = os.environ.copy()
        environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
        result = subprocess.run([str(INSTALL_ROOT / "Pointer.exe"), "--apply", "--quiet", "--report", str(report)],
                                env=environment, creationflags=0x08000000, timeout=30)
        detail = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
        if result.returncode or detail.get("exit_code") != 0:
            raise RuntimeError(detail.get("error", "安装后的配置程序未成功完成。"))
        remove_obsolete_files(previous_files, files, INSTALL_ROOT)
    else:
        _shortcuts()
        from pointer.cli import apply_theme
        apply_theme()
    return {"installed": True, "install_directory": str(INSTALL_ROOT.resolve()),
            "backup_directory": str(DATA_ROOT.resolve()), "startup_enabled": True}

