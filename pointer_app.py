"""Provide packaged installation, recovery, and background entry points.

Resources live beside the EXE. Backups live outside that folder so installing a
new release cannot replace the settings needed to restore the original cursor.
"""

import argparse
import base64
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import time
import winreg

import adaptive_switcher as switcher
import configure_cursor as config
from contrast_theme import THEME_NAME, theme_paths
from runtime_paths import DATA_ROOT, FROZEN, INSTALL_ROOT, ROOT


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


def diagnose():
    switcher._set_dpi_awareness()
    files = package_files(ROOT) if FROZEN else {}
    count = animated = 0
    for theme in ("light", "dark"):
        for path in theme_paths(theme).values():
            cursor = switcher._CursorCache._load(path)
            try:
                if path.suffix.lower() == ".ani":
                    if not switcher._has_animation(cursor):
                        raise ValueError(f"Animation has no distinct frames: {path.name}")
                    animated += 1
                count += 1
            finally:
                switcher.USER32.DestroyCursor(cursor)
    return {"cursor_resources": count, "animated_resources": animated,
            "package_files": len(files), "frozen": FROZEN}


def _snapshot():
    schemes = config.read_values(config.SCHEME_PATH)
    return {"cursor_values": config.read_values(config.KEY_PATH),
            "scheme_name": THEME_NAME,
            "previous_named_scheme": schemes.get(THEME_NAME),
            "additional_named_schemes": {config.SCHEME_NAME: schemes.get(config.SCHEME_NAME)}}


def _run_value():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, switcher.RUN_KEY) as key:
            value, kind = winreg.QueryValueEx(key, switcher.RUN_VALUE)
        return {"value": value, "type": kind}
    except FileNotFoundError:
        return None


def apply_theme():
    """Roll back this operation if the background helper cannot become ready."""
    before, run_before = _snapshot(), _run_value()
    startup_before = switcher.STARTUP_BACKUP.read_bytes() if switcher.STARTUP_BACKUP.exists() else None
    if config.BACKUP.exists():
        config.validate_backup(json.loads(config.BACKUP.read_text(encoding="utf-8")))
    try:
        switcher.stop()
        config.apply(dual=True)
        switcher.enable_startup()
        state = switcher.start()
        return {"running": state["running"], "pid": state["pid"], "startup_enabled": True}
    except Exception as error:
        recovery_errors = []
        def recover(operation):
            try:
                operation()
            except Exception as recovery_error:
                recovery_errors.append(str(recovery_error))
        def restore_run():
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, switcher.RUN_KEY,
                                   0, winreg.KEY_SET_VALUE) as key:
                config.restore_value(key, switcher.RUN_VALUE, run_before)
        def restore_startup_backup():
            if startup_before is None:
                switcher.STARTUP_BACKUP.unlink(missing_ok=True)
            else:
                switcher.STARTUP_BACKUP.write_bytes(startup_before)
        # Each recovery step must run even if another one fails.
        recover(lambda: switcher.stop_directory(ROOT))
        recover(lambda: config.restore_values(before))
        recover(config.reload_cursors)
        recover(restore_run)
        recover(restore_startup_backup)
        if recovery_errors:
            raise RuntimeError(f"{error}; recovery failed: {'; '.join(recovery_errors)}") from error
        raise


def stop_theme():
    result = switcher.stop()
    if switcher._scheme_name() == THEME_NAME:
        config.reload_cursors()
    return {"running": False, "startup_enabled": False,
            "shutdown_reason": result.get("shutdown_reason")}


def reference_theme():
    switcher.stop()
    config.apply()
    return {"running": False, "startup_enabled": False, "fixed_reference": True}


def restore_theme():
    if not config.BACKUP.exists():
        raise ValueError("没有找到原光标备份，请先完成安装。")
    config.validate_backup(json.loads(config.BACKUP.read_text(encoding="utf-8")))
    switcher.stop()
    config.restore()
    return {"restored": True, "running": False, "startup_enabled": False}


def _previous_directory():
    arrow = config.read_values(config.KEY_PATH).get("Arrow", {}).get("value", "")
    path = Path(os.path.expandvars(arrow)) if isinstance(arrow, str) and arrow else None
    if not path:
        return None
    if path.name == "adaptive-arrow.cur" and path.parent.name in ("light", "dark"):
        root = path.parent.parent.parent
        if path.parent.parent.name != "dual-contrast":
            return None
    elif path.name in ("reference-black-arrow.cur", "adaptive-arrow.cur"):
        root = path.parent.parent if path.parent.name == "adaptive" else path.parent
    else:
        return None
    root = root.resolve()
    if (root / "configure_cursor.py").is_file() or (root / "Pointer.exe").is_file():
        return root
    return None


def _migrate_backup(previous):
    """Copy only this user's backup; downloaded packages never contain one."""
    if config.BACKUP.exists():
        config.validate_backup(json.loads(config.BACKUP.read_text(encoding="utf-8")))
        return
    if not previous:
        return
    old_backup = previous / config.BACKUP.name
    if old_backup.is_file():
        config.save_backup(config.validate_backup(json.loads(old_backup.read_text(encoding="utf-8"))))
    old_startup = previous / switcher.STARTUP_BACKUP.name
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
             ("恢复原光标", "--restore"), ("打开测试页", "--test-page")]
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


def install():
    if not FROZEN:
        raise ValueError("源码模式请使用 --apply；一键安装请运行发布包中的 Pointer.exe。")
    files = package_files(ROOT)
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
    else:
        _shortcuts()
        apply_theme()
    return {"installed": True, "install_directory": str(INSTALL_ROOT.resolve()),
            "backup_directory": str(DATA_ROOT.resolve()), "startup_enabled": True}


def dispatch(action):
    """Downloaded control buttons always operate on the installed helper."""
    installed = INSTALL_ROOT / "Pointer.exe"
    if FROZEN and ROOT.resolve() != INSTALL_ROOT.resolve() and action in (
            "apply", "stop", "restore", "reference", "test_page"):
        if installed.is_file():
            report = DATA_ROOT / "delegated-operation.json"
            environment = os.environ.copy()
            environment["PYINSTALLER_RESET_ENVIRONMENT"] = "1"
            completed = subprocess.run([str(installed), "--" + action.replace("_", "-"),
                                        "--quiet", "--report", str(report)],
                                       env=environment, creationflags=0x08000000, timeout=30)
            value = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
            if completed.returncode or value.get("exit_code") != 0:
                raise RuntimeError(value.get("error", "安装版未成功完成操作。"))
            return value
        if action == "apply":
            return install()
        if action != "test_page":
            raise ValueError("尚未安装 Pointer，请先运行一键安装.cmd。")
    if action == "test_page":
        os.startfile(ROOT / "cursor-test" / "index.html")
        return {"test_page_opened": True}
    operation = {"install": install, "apply": apply_theme, "stop": stop_theme,
                 "reference": reference_theme, "restore": restore_theme, "diagnose": diagnose}[action]
    return operation()


def main(argv=None):
    # Windowed builds have no streams, but shared configuration code prints.
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()
    parser = argparse.ArgumentParser(description="Pointer cursor installer")
    group = parser.add_mutually_exclusive_group()
    for action in ("install", "apply", "stop", "restore", "reference", "run", "diagnose", "test-page"):
        group.add_argument("--" + action, action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)
    if args.run:
        switcher._run()
        return 0
    action = next((name for name in ("apply", "stop", "restore", "reference", "diagnose", "test_page")
                   if getattr(args, name)), "install")
    result = {"action": action, "exit_code": 0}
    messages = {"install": "安装完成。自适应光标已启用，并随 Windows 登录启动。\n可在开始菜单的 Pointer 文件夹中停止切换或恢复原光标。",
                "apply": "自适应光标已启用。", "stop": "已停止自动切换并取消登录启动。当前保留黑色主体、白色边框。",
                "restore": "已恢复原来的 Windows 光标。", "reference": "已启用固定黑色主体、灰白边框的原始造型。",
                "diagnose": "发布包和光标资源检查通过。"}
    try:
        result.update(dispatch(action))
    except Exception as error:
        result.update(exit_code=1, error=f"{type(error).__name__}: {error}")
    report = args.report or DATA_ROOT / "last-operation.json"
    switcher._atomic_json(report, result)
    if not args.quiet and action != "test_page":
        message = result.get("error", messages[action])
        ctypes.windll.user32.MessageBoxW(None, message, "Pointer", 0x10 if result["exit_code"] else 0x40)
    print(json.dumps(result, ensure_ascii=False))
    return result["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
