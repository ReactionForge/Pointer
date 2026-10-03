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
        except Exception:
            if target.exists():
                os.replace(target,stage)
            if rollback.exists():
                os.replace(rollback,target)
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
        config.validate_backup(json.loads(old_backup.read_text(encoding="utf-8")))
        config.BACKUP.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(old_backup,config.BACKUP)
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


def _execute(executable, arguments, report):
    environment = os.environ.copy()
    environment['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
    completed = subprocess.run([str(executable), *arguments, '--quiet', '--report', str(report)],
                               env=environment,creationflags=0x08000000,timeout=180)
    result = json.loads(report.read_text(encoding='utf-8')) if report.exists() else {}
    if completed.returncode or result.get('exit_code') != 0:
        raise RuntimeError(result.get('error','安装程序未成功完成操作'))
    return result


def install():
    if not FROZEN:
        raise ValueError('请使用发布包安装；源码模式可直接打开设置界面。')
    files = package_files(ROOT)
    from .backend import WindowsBackend
    backend = WindowsBackend(DATA_ROOT,INSTALL_ROOT)
    before = backend.snapshot()
    saved_files = {DATA_ROOT/name: (DATA_ROOT/name).read_bytes() if (DATA_ROOT/name).exists() else None
                   for name in ('settings.json','click-motion-settings.json','active-profile.json',
                                'original-cursor-settings.json','contrast-switcher-startup-backup.json')}
    standard = Path(os.environ['LOCALAPPDATA'])/'Pointer'/'app'
    previous = _previous_directory() if INSTALL_ROOT.resolve() == standard.resolve() or not os.environ.get('POINTER_DATA_DIR') else None
    if previous and previous != INSTALL_ROOT:
        package_files(previous)
        previous_data = previous.parent/'data'
        DATA_ROOT.mkdir(parents=True,exist_ok=True)
        for name in ('settings.json','click-motion-settings.json','contrast-switcher-startup-backup.json'):
            source = previous_data/name
            destination = DATA_ROOT/name
            if source.exists() and not destination.exists():
                shutil.copy2(source,destination)
    _migrate_backup(previous)
    upgrade_state = None
    if (INSTALL_ROOT/'PACKAGE.json').is_file():
        package_files(INSTALL_ROOT)
    was_running = switcher.running_directory(INSTALL_ROOT,DATA_ROOT,_legacy=True)
    if previous:
        package_files(previous)
        was_running = was_running or switcher.running_directory(previous,previous.parent/'data',_legacy=True)
    if (INSTALL_ROOT/'PACKAGE.json').is_file() and ROOT != INSTALL_ROOT:
        package_files(INSTALL_ROOT)
        version = (INSTALL_ROOT/'VERSION').read_text().strip()
        if tuple(int(v) for v in version.split('-')[0].split('.')) >= (1,3,0):
            report = DATA_ROOT/'prepare-install-report.json'
            upgrade_state = _execute(INSTALL_ROOT/'Pointer.exe',['--prepare-upgrade'],report)
        else:
            switcher.stop_directory(INSTALL_ROOT,DATA_ROOT,_legacy=True)
            upgrade_state={'previously_running':was_running}
    if previous and previous != INSTALL_ROOT:
        package_files(previous)
        switcher.stop_directory(previous,previous.parent/'data',_legacy=True)
    switcher.stop_directory(INSTALL_ROOT,DATA_ROOT)
    def finalize():
        if not os.environ.get('POINTER_INSTALL_DIR'):
            _shortcuts()
        if previous and previous != INSTALL_ROOT and backend.startup_enabled():
            from .startup import enable_startup
            enable_startup()
        if was_running or (upgrade_state and upgrade_state.get('previously_running')):
            _execute(INSTALL_ROOT/'Pointer.exe',['--apply'],DATA_ROOT/'upgrade-resume-report.json')
    try:
        deploy_package(ROOT,INSTALL_ROOT,finalize=finalize)
    except Exception as error:
        from pointer.cursor.settings import _write_bytes
        try:
            for path,content in saved_files.items():
                if content is None:
                    path.unlink(missing_ok=True)
                else:
                    _write_bytes(path,content)
            backend.restore({**before,'running':False,'previous_root':None})
            if was_running:
                recovery_root = previous if previous and previous != INSTALL_ROOT else INSTALL_ROOT
                recovery_data = recovery_root.parent/'data'
                _execute(recovery_root/'Pointer.exe',['--apply','--install-dir',str(recovery_root),'--data-dir',str(recovery_data)],recovery_data/'rollback-resume-report.json')
        except Exception as failure:
            raise RuntimeError(f'{error}；恢复失败：{failure}') from error
        raise
    return {'installed':True,'install_directory':str(INSTALL_ROOT),'backup_directory':str(DATA_ROOT),
            'startup_enabled':False if not (DATA_ROOT/'settings.json').exists() else
                json.loads((DATA_ROOT/'settings.json').read_text(encoding='utf-8')).get('startup',False)}


def apply_portable(settings):
    from pointer.cursor.settings import _write_json
    if not (INSTALL_ROOT/'PACKAGE.json').exists() or package_files(ROOT) != package_files(INSTALL_ROOT):
        install()
    token = uuid.uuid4().hex
    desired, report = DATA_ROOT/f'portable-{token}.json', DATA_ROOT/f'portable-{token}-report.json'
    _write_json(desired,settings.to_dict())
    try:
        return _execute(INSTALL_ROOT/'Pointer.exe',['--apply','--settings-file',str(desired)],report)
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
