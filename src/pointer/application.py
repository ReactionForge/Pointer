"""Coordinate preferences, prepared resources and reversible Windows operations."""
from dataclasses import replace
import json
from pathlib import Path
import threading

from .cursor.settings import CursorSettings, SettingsStore, _write_json
from .cursor.resources import prepare_resources


class Application:
    def __init__(self, data_root, install_root, backend=None):
        self.data_root, self.install_root = Path(data_root), Path(install_root)
        self.store = SettingsStore(self.data_root)
        self.profile_path = self.data_root / 'active-profile.json'
        self._lock = threading.RLock()
        if backend is None:
            from .windows.backend import WindowsBackend
            backend = WindowsBackend(self.data_root, self.install_root)
        self.backend = backend

    def settings(self):
        return self.store.load(legacy_mode_path=self.data_root / 'click-motion-settings.json',
                               startup_enabled=self.backend.startup_enabled())

    def snapshot(self):
        return {**self.backend.snapshot(), 'settings': self.settings().to_dict(), 'last_error': None}

    def apply(self, settings):
        settings = CursorSettings.from_dict(settings.to_dict())
        from .paths import FROZEN, ROOT
        if FROZEN and ROOT.resolve() != self.install_root.resolve():
            from .windows.installation import apply_portable
            return apply_portable(settings)
        with self._lock:
            bundle = prepare_resources(settings, self.data_root / 'cursor-cache')
            before = self.backend.snapshot()
            files = {path: path.read_bytes() if path.exists() else None
                     for path in (self.store.path, self.profile_path)}
            profile = {'key': bundle.key, 'size': bundle.size, 'settings': settings.to_dict(),
                       'themes': {theme: {role: str(path) for role, path in bundle.paths(theme).items()}
                                  for theme in ('light', 'dark')},
                       'frames': {f'{theme}:{frame}': {role: str(path) for role, path in bundle.paths(theme, frame).items()
                                                      if role in ('Arrow', 'Hand')}
                                  for theme in ('light', 'dark') for frame in range(5)}}
            try:
                self.backend.stop()
                self.store.save(settings)
                _write_json(self.profile_path, profile)
                self.backend.apply(bundle, settings.appearance)
                if self.backend.startup_enabled() != settings.startup:
                    self.backend.set_startup(settings.startup)
                state = self.backend.start()
                if not state.get('running'):
                    raise RuntimeError('后台服务未就绪')
                return {**state, 'startup_enabled': settings.startup,
                        'settings': settings.to_dict(), 'last_error': None}
            except Exception as error:
                recovery = []
                for path, content in files.items():
                    try:
                        if content is None:
                            path.unlink(missing_ok=True)
                        else:
                            from .cursor.settings import _write_bytes
                            _write_bytes(path, content)
                    except Exception as failure:
                        recovery.append(str(failure))
                try:
                    self.backend.restore(before)
                except Exception as failure:
                    recovery.append(str(failure))
                if recovery:
                    raise RuntimeError(f'{error}；恢复失败：' + '；'.join(recovery)) from error
                raise

    def pause(self):
        with self._lock:
            settings = self.settings()
            self.backend.stop()
            return {'running': False, 'startup_enabled': self.backend.startup_enabled(),
                    'settings': settings.to_dict(), 'last_error': None}

    def resume(self):
        return self.apply(self.settings())

    def restore(self):
        with self._lock:
            settings = self.settings()
            before = self.backend.snapshot()
            self.backend.restore_original()
            try:
                self.store.save(replace(settings, startup=False))
            except Exception:
                self.backend.restore(before)
                raise
            return {'running': False, 'startup_enabled': False, 'restored': True,
                    'settings': self.store.load().to_dict(), 'last_error': None}

    def set_startup(self, enabled):
        if type(enabled) is not bool:
            raise ValueError('开机启动必须是布尔值')
        with self._lock:
            settings = self.settings()
            before = self.backend.snapshot()
            try:
                if self.backend.startup_enabled() != enabled:
                    self.backend.set_startup(enabled)
                self.store.save(replace(settings, startup=enabled))
            except Exception:
                self.backend.restore(before)
                raise
            return {'startup_enabled': enabled}

    def prepare_upgrade(self):
        with self._lock:
            from .windows.gui_ipc import prepare_gui_upgrade
            prepare_gui_upgrade()
            before = self.snapshot()
            self.backend.stop()
            _write_json(self.data_root / 'upgrade-state.json', before)
            return {'ready': True, 'previously_running': before['running']}
