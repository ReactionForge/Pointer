"""Verified package installation, migration and owned-file cleanup."""
import base64, hashlib, json, os, shutil, subprocess, time, tempfile, uuid
from pathlib import Path, PurePosixPath
from pointer.paths import ROOT, DATA_ROOT, INSTALL_ROOT, FROZEN, INSTALLATION_MARKER, is_installed
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


def _remove_temporary(path, parent, prefix):
    path, parent = Path(path).resolve(), Path(parent).resolve()
    if path.parent != parent or not path.name.startswith(prefix):
        raise ValueError('拒绝清理管理范围外的目录')
    if path.exists():
        shutil.rmtree(path)


def deploy_package(source, target, finalize=None):
    """Validate and stage a complete deployment, then replace or recover it."""
    source, target = Path(source).resolve(), Path(target).resolve()
    files = package_files(source)
    if source == target:
        if finalize:
            finalize()
        return files
    if target == target.parent or source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError('程序来源与安装目录不能相互包含')
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.pointer-stage-',dir=target.parent))
    rollback = target.parent / ('.pointer-rollback-'+uuid.uuid4().hex)
    previous = {}
    try:
        if target.exists():
            for path in target.rglob('*'):
                if path.is_symlink() or not path.resolve().is_relative_to(target):
                    raise ValueError('安装目录包含外部链接，请先移除链接')
            shutil.copytree(target,stage,dirs_exist_ok=True)
            if (target/'PACKAGE.json').exists():
                previous = json.loads((target/'PACKAGE.json').read_text(encoding='utf-8')).get('files',{})
        for name in (*files,'PACKAGE.json'):
            if (target/name).exists() and name not in previous and name != 'PACKAGE.json':
                raise ValueError(f'安装目录存在同名用户文件：{name}')
            destination = stage/name
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source/name,destination)
        remove_obsolete_files(previous,files,stage)
        package_files(stage)
        from pointer.cursor.settings import _write_json
        _write_json(stage/INSTALLATION_MARKER,{'schema_version':1,'data_directory':'../data'})
        if target.exists():
            os.replace(target,rollback)
        try:
            os.replace(stage,target)
            package_files(target)
            if finalize:
                finalize()
        except Exception as error:
            recovery = []
            try:
                if target.exists():
                    os.replace(target, stage)
            except Exception as failure:
                recovery.append(str(failure))
            try:
                if rollback.exists():
                    os.replace(rollback, target)
            except Exception as failure:
                recovery.append(str(failure))
            if recovery:
                raise RuntimeError(f'{error}；恢复失败：' + '；'.join(recovery)) from error
            raise
        _remove_temporary(rollback,target.parent,'.pointer-rollback-')
        return files
    finally:
        _remove_temporary(stage,target.parent,'.pointer-stage-')


def _previous_directory():
    arrow = config.read_values(config.KEY_PATH).get("Arrow", {}).get("value", "")
    path = Path(os.path.expandvars(arrow)) if isinstance(arrow, str) and arrow else None
    if not path:
        return None
    if (path.name == 'adaptive-arrow.cur' and path.parent.name in ('light','dark')
            and path.parents[2].name == 'cursor-cache' and path.parents[3].name == 'data'):
        data = path.parents[3].resolve()
        if data.parent.name == '.local':
            candidate = data.parent.parent
            if (candidate/'src/pointer/windows/engine.py').is_file():
                return candidate
        for candidate in data.parent.iterdir():
            if candidate.is_dir() and candidate != data and (candidate/'Pointer.exe').is_file():
                if is_installed(candidate) or (candidate.name == 'app' and candidate.parent.name == 'Pointer'):
                    package_files(candidate)
                    return candidate.resolve()
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
        from pointer.cursor.settings import _write_bytes
        content = old_backup.read_bytes()
        config.validate_backup(json.loads(content.decode('utf-8')))
        _write_bytes(config.BACKUP, content)
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
    pairs = [("Pointer", "--gui"), ("光标测试", "--test-page")]
    def literal(value):
        return "'" + str(value).replace("'", "''") + "'"
    commands = ["$pointerShell = New-Object -ComObject WScript.Shell"]
    for title, arguments in pairs:
        commands.extend([f"$pointerShortcut = $pointerShell.CreateShortcut({literal(menu / (title + '.lnk'))})",
                         f"$pointerShortcut.TargetPath = {literal(executable)}",
                         f"$pointerShortcut.Arguments = {literal(arguments)}",
                         f"$pointerShortcut.WorkingDirectory = {literal(INSTALL_ROOT.resolve())}",
                         f"$pointerShortcut.IconLocation = {literal(str(INSTALL_ROOT.resolve() / 'pointer.ico') + ',0')}",
                         "$pointerShortcut.Save()"])
    encoded = base64.b64encode("\n".join(commands).encode("utf-16-le")).decode("ascii")
    startup_info = subprocess.STARTUPINFO()
    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup_info.wShowWindow = 0
    subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
                   check=True, creationflags=0x08000000, startupinfo=startup_info,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


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


def _execute(executable, arguments, report, *, upgrade_resume=False):
    report.unlink(missing_ok=True)
    environment = os.environ.copy()
    environment.pop('POINTER_UPGRADE_HANDOFF', None)
    if upgrade_resume:
        environment['POINTER_UPGRADE_HANDOFF'] = str((report.parent/'upgrade-state.json').resolve())
    environment['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    startup_info = subprocess.STARTUPINFO()
    startup_info.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup_info.wShowWindow = 0
    completed = subprocess.run([str(executable), *arguments, '--quiet', '--report', str(report)],
                               env=environment, creationflags=0x08000000, startupinfo=startup_info,
                               stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=180)
    result = json.loads(report.read_text(encoding='utf-8')) if report.exists() else {}
    if completed.returncode or result.get('exit_code') != 0:
        raise RuntimeError(result.get('error','安装程序未成功完成操作'))
    return result


def _upgrade_handoff(data_root, install_root, current, previous=None):
    """Read a recent matching handoff; previous must be a verified installation."""
    from pointer.cursor.settings import CursorSettings, _read_json
    path = data_root/'upgrade-state.json'
    try:
        if not 0 <= time.time() - path.stat().st_mtime <= 15 * 60:
            return None
        content = path.read_bytes()
        if len(content) > 65536:
            return None
        saved = json.loads(content.decode('utf-8'))
        saved_previous = saved.get('previous_root')
        previous_running = bool(previous and isinstance(saved_previous, str)
                                and Path(saved_previous).resolve() == previous.resolve())
        if (type(saved.get('running')) is not bool or
                (saved['running'] is not True and not previous_running) or not all(
                    key in saved and saved[key] == current.get(key)
                    for key in ('registry', 'run', 'startup_backup'))):
            return None
        config.validate_backup(saved['registry'])
        if (CursorSettings.from_dict(saved.get('settings')).to_dict() !=
                CursorSettings.from_dict(_read_json(data_root/'settings.json')).to_dict()):
            return None
        # Older snapshots have no directory IDs. Bind their cursor path to the
        # exact target, or to the separately verified previous install/cache.
        arrow = saved['registry']['cursor_values'].get('Arrow', {}).get('value')
        if not isinstance(arrow, str) or not arrow:
            return None
        cursor = Path(os.path.expandvars(arrow)).resolve()
        managed_roots = []
        if saved.get('running') is True:
            managed_roots.extend((data_root/'cursor-cache', install_root))
        if previous_running:
            managed_roots.extend((previous.parent/'data'/'cursor-cache', previous))
        if not any(cursor.is_relative_to(root.resolve()) for root in managed_roots):
            return None
        for key, root in (('upgrade_install_root', install_root), ('upgrade_data_root', data_root)):
            if key in saved and Path(saved[key]).resolve() != root.resolve():
                return None
        return saved, content
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def install():
    if not FROZEN:
        raise ValueError('请使用发布包安装；源码模式可直接打开设置界面。')
    package_files(ROOT)
    from .backend import WindowsBackend
    from .gui_ipc import prepare_gui_upgrade
    from pointer.cursor.settings import _write_bytes

    # This IPC gate rejects dirty/busy windows and waits for the installed GUI
    # to exit. Never call the old executable's --prepare-upgrade a second time.
    prepare_gui_upgrade()
    backend = WindowsBackend(DATA_ROOT, INSTALL_ROOT)
    before = backend.snapshot()
    saved_files = {DATA_ROOT/name: (DATA_ROOT/name).read_bytes() if (DATA_ROOT/name).exists() else None
                   for name in ('settings.json', 'click-motion-settings.json', 'active-profile.json',
                                'original-cursor-settings.json', 'contrast-switcher-startup-backup.json')}
    standard = Path(os.environ['LOCALAPPDATA'])/'Pointer'/'app'
    previous = _previous_directory() if INSTALL_ROOT.resolve() == standard.resolve() or not os.environ.get('POINTER_DATA_DIR') else None
    if (INSTALL_ROOT/'PACKAGE.json').is_file():
        package_files(INSTALL_ROOT)
    previous = previous if previous and previous.resolve() != INSTALL_ROOT.resolve() else None
    if previous:
        package_files(previous)
    installed_running = bool(before.get('running') or switcher.running_directory(INSTALL_ROOT, DATA_ROOT, _legacy=True))
    previous_running = bool(previous and switcher.running_directory(previous, previous.parent/'data', _legacy=True))
    handoff = _upgrade_handoff(DATA_ROOT, INSTALL_ROOT, before, previous)
    saved = handoff[0] if handoff else {}
    handoff_installed = saved.get('running') is True
    handoff_previous = bool(previous and isinstance(saved.get('previous_root'), str)
                           and Path(saved['previous_root']).resolve() == previous.resolve())
    # Live state wins, but consume matching old intent even if it is not needed.
    runtime_changed = bool((handoff_installed and not installed_running) or
                           (handoff_previous and not previous_running))
    installed_running = installed_running or handoff_installed
    previous_running = previous_running or handoff_previous
    was_running = installed_running or previous_running

    def consume_handoff():
        if handoff:
            path = DATA_ROOT/'upgrade-state.json'
            try:
                if path.read_bytes() == handoff[1]:
                    path.unlink()
            except FileNotFoundError:
                pass

    def resume(root, data, report):
        result = _execute(root/'Pointer.exe', ['--apply', '--install-dir', str(root), '--data-dir', str(data)],
                          data/report, upgrade_resume=True)
        if result.get('running') is not True:
            raise RuntimeError('升级后后台服务未就绪')

    def finalize():
        if not os.environ.get('POINTER_INSTALL_DIR'):
            _shortcuts()
        if previous and backend.startup_enabled():
            from .startup import enable_startup
            enable_startup()
        if was_running:
            resume(INSTALL_ROOT, DATA_ROOT, 'upgrade-resume-report.json')
        consume_handoff()

    try:
        if previous:
            previous_data = previous.parent/'data'
            DATA_ROOT.mkdir(parents=True, exist_ok=True)
            for name in ('settings.json', 'click-motion-settings.json', 'contrast-switcher-startup-backup.json'):
                source, destination = previous_data/name, DATA_ROOT/name
                if source.exists() and not destination.exists():
                    shutil.copy2(source, destination)
        _migrate_backup(previous)
        # Keep the first runtime intent in memory; stop may refresh status files.
        runtime_changed = True
        for root, data in ([(previous, previous.parent/'data')] if previous else []) + [(INSTALL_ROOT, DATA_ROOT)]:
            switcher.stop_directory(root, data)
            if switcher.running_directory(root, data, _legacy=True):
                switcher.stop_directory(root, data, _legacy=True)
        deploy_package(ROOT, INSTALL_ROOT, finalize=finalize)
    except Exception as error:
        recovery = []
        for path, content in saved_files.items():
            try:
                if content is None:
                    # A first original-cursor backup remains useful after a failed
                    # install. Never discard it along with temporary preferences.
                    if path.name != 'original-cursor-settings.json':
                        path.unlink(missing_ok=True)
                elif not path.exists() or path.read_bytes() != content:
                    _write_bytes(path, content)
            except Exception as failure:
                recovery.append(str(failure))
        if runtime_changed:
            try:
                backend.restore({**before, 'running': False, 'previous_root': None})
            except Exception as failure:
                recovery.append(str(failure))
            if not recovery:
                for root, data, running in ((INSTALL_ROOT, DATA_ROOT, installed_running),
                                            (previous, previous.parent/'data' if previous else None, previous_running)):
                    if running:
                        try:
                            resume(root, data, 'rollback-resume-report.json')
                        except Exception as failure:
                            recovery.append(str(failure))
        if not recovery:
            try:
                consume_handoff()
            except Exception as failure:
                recovery.append(str(failure))
        if recovery:
            raise RuntimeError(f'{error}；恢复失败：' + '；'.join(recovery)) from error
        raise
    return {'installed': True, 'install_directory': str(INSTALL_ROOT), 'backup_directory': str(DATA_ROOT),
            'startup_enabled': False if not (DATA_ROOT/'settings.json').exists() else
                json.loads((DATA_ROOT/'settings.json').read_text(encoding='utf-8')).get('startup', False)}


def apply_portable(settings, *, preserve_runtime=False, preserve_upgrade_handoff=False):
    from pointer.cursor.settings import _write_json
    if not (INSTALL_ROOT/'PACKAGE.json').exists() or package_files(ROOT) != package_files(INSTALL_ROOT):
        install()
    token = uuid.uuid4().hex
    desired, report = DATA_ROOT/f'portable-{token}.json', DATA_ROOT/f'portable-{token}-report.json'
    _write_json(desired,settings.to_dict())
    try:
        arguments = ['--apply', '--settings-file', str(desired)]
        if preserve_runtime:
            arguments.append('--preserve-runtime')
        return _execute(INSTALL_ROOT/'Pointer.exe', arguments, report, upgrade_resume=preserve_upgrade_handoff)
    finally:
        desired.unlink(missing_ok=True)
        report.unlink(missing_ok=True)


def uninstall(purge=False):
    from pointer.application import Application
    from .gui_ipc import prepare_gui_upgrade
    prepare_gui_upgrade()
    application = Application(DATA_ROOT,INSTALL_ROOT)
    if application.backend.backup.exists():
        application.restore()
    else:
        current = config.read_values(config.KEY_PATH).get('Arrow',{}).get('value','')
        if current and (Path(current).resolve().is_relative_to(ROOT) or
                        Path(current).resolve().is_relative_to(DATA_ROOT/'cursor-cache')):
            raise ValueError('当前光标仍使用 Pointer，但原光标备份缺失；卸载已中止。')
        application.backend.stop()
        application.backend.set_startup(False)
    manifest = json.loads((ROOT/'PACKAGE.json').read_text(encoding='utf-8'))
    files = manifest.get('files',{})
    if not isinstance(files,dict) or 'Pointer.exe' not in files:
        raise ValueError('程序清单损坏，卸载已中止')
    lines = []
    for name,digest in files.items():
        path = (ROOT/name).resolve()
        if not path.is_relative_to(ROOT) or not isinstance(digest,str) or len(digest)!=64:
            raise ValueError('程序清单含无效路径')
        lines.append(name+'|'+digest)
    lines.append('PACKAGE.json|'+hashlib.sha256((ROOT/'PACKAGE.json').read_bytes()).hexdigest())
    if (ROOT/INSTALLATION_MARKER).exists():
        is_installed(ROOT)
        lines.append(INSTALLATION_MARKER+'|'+hashlib.sha256((ROOT/INSTALLATION_MARKER).read_bytes()).hexdigest())
    DATA_ROOT.mkdir(parents=True,exist_ok=True)
    (DATA_ROOT/'uninstall-owned-files.txt').write_text('\n'.join(lines),encoding='utf-8')
    if purge:
        allowed = INSTALL_ROOT.parent/'data'
        if DATA_ROOT.resolve() != allowed.resolve():
            raise ValueError('配置目录不在安装目录旁，拒绝自动清除')
        for name in ('settings.json','click-motion-settings.json','active-profile.json','upgrade-state.json'):
            (DATA_ROOT/name).unlink(missing_ok=True)
    return {'uninstalled':True,'settings_preserved':not purge}
