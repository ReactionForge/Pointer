"""Keep Windows mutations behind a reversible application boundary."""
import json
import os
from pathlib import Path
import subprocess
import winreg
from pointer.paths import ROOT
from pointer.cursor.settings import _write_bytes
from . import engine, scheme, startup


def _run_value():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, startup.RUN_KEY) as key:
            value, kind = winreg.QueryValueEx(key, startup.RUN_VALUE)
            return {'value': value, 'type': kind}
    except FileNotFoundError:
        return None


class WindowsBackend:
    def __init__(self, data_root, install_root):
        self.data_root, self.install_root = Path(data_root), Path(install_root)
        self.backup = self.data_root / 'original-cursor-settings.json'

    def startup_enabled(self):
        value = _run_value()
        if value is None or value['type'] != winreg.REG_SZ:
            return False
        expected = startup._startup_command()
        backup_path = self.data_root / startup.STARTUP_BACKUP.name
        if backup_path.exists():
            backup = json.loads(backup_path.read_text(encoding='utf-8'))
            expected = backup.get('installed_command', expected)
        return value['value'] == expected

    def snapshot(self):
        schemes = scheme.read_values(scheme.SCHEME_PATH)
        backup_path = self.data_root / startup.STARTUP_BACKUP.name
        previous = self.previous_installation()
        previous_running = bool(previous and engine.running_directory(previous,previous.parent/'data'))
        return {'registry': {'cursor_values': scheme.read_values(scheme.KEY_PATH),
                             'scheme_name': scheme.ADAPTIVE_SCHEME_NAME,
                             'previous_named_scheme': schemes.get(scheme.ADAPTIVE_SCHEME_NAME)},
                'run': _run_value(), 'running': engine._running(),
                'previous_root': str(previous) if previous_running else None,
                'startup_enabled': self.startup_enabled(),
                'startup_backup': backup_path.read_text(encoding='utf-8') if backup_path.exists() else None}

    def stop(self):
        previous = self.previous_installation()
        if previous and previous != ROOT:
            engine.stop_directory(previous,previous.parent/'data')
        return engine.stop_directory(ROOT, self.data_root)

    def previous_installation(self):
        if os.environ.get('POINTER_DATA_DIR'):
            return None
        from .installation import _previous_directory, package_files
        previous = _previous_directory()
        if previous and (previous/'PACKAGE.json').is_file():
            package_files(previous)
            return previous
        return None

    def set_startup(self, enabled):
        return startup.enable_startup() if enabled else startup.disable_startup()

    def apply(self, bundle, appearance):
        theme = appearance if appearance in ('light', 'dark') else 'light'
        scheme.apply_paths(bundle.paths(theme), backup_path=self.backup, canvas_size=bundle.size)

    def start(self):
        return engine.start()

    def restore(self, before):
        self.stop()
        scheme.restore_values(before['registry'])
        scheme.reload_cursors()
        if _run_value() != before['run']:
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, startup.RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
                scheme.restore_value(key, startup.RUN_VALUE, before['run'])
        path = self.data_root / startup.STARTUP_BACKUP.name
        if before['startup_backup'] is None:
            path.unlink(missing_ok=True)
        else:
            _write_bytes(path, before['startup_backup'].encode('utf-8'))
        if before['running']:
            self.start()
        elif before.get('previous_root'):
            from .installation import package_files
            previous = Path(before['previous_root'])
            package_files(previous)
            environment = os.environ.copy()
            environment['PYINSTALLER_RESET_ENVIRONMENT'] = '1'
            subprocess.Popen([str(previous/'Pointer.exe'),'--run'],cwd=previous,env=environment,
                             creationflags=0x08000000,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)

    def restore_original(self):
        # Validate first: a damaged backup must not stop the working service.
        scheme.validate_backup(json.loads(self.backup.read_text(encoding='utf-8')))
        before = self.snapshot()
        try:
            self.stop()
            scheme.restore(self.backup)
            self.set_startup(False)
        except Exception:
            self.restore(before)
            raise
