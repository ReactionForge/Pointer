"""Validated user preferences with atomic storage and explicit legacy migration."""
from dataclasses import asdict, dataclass, fields
import json
import os
from pathlib import Path
import re
import uuid

MAX_JSON_BYTES = 65536
SIZES = (24, 32, 40, 48, 64)
STYLES = ('sequoia', 'precision', 'falcon', 'pixel')
MOTIONS = ('tilt', 'shrink', 'spring', 'pulse', 'trail', 'off')


@dataclass(frozen=True)
class CursorSettings:
    schema_version: int = 1
    appearance: str = 'adaptive'
    light_body: str = '#000000'
    light_outline: str = '#ffffff'
    dark_body: str = '#ffffff'
    dark_outline: str = '#000000'
    size: int = 32
    motion: str = 'tilt'
    strength: int = 50
    press_ms: int = 60
    release_ms: int = 150
    startup: bool = False
    style: str = 'sequoia'
    aura_glow: bool = False
    aura_color: str = '#007aff'
    shake_to_find: bool = True
    game_dnd: bool = True
    tray_enabled: bool = True
    auto_check_update: bool = True
    skip_update_version: str = ''

    def __post_init__(self):
        bounds = {'schema_version': (1, 1), 'strength': (0, 100),
                  'press_ms': (40, 200), 'release_ms': (80, 400)}
        for name, (lower, upper) in bounds.items():
            value = getattr(self, name)
            if type(value) is not int or not lower <= value <= upper:
                raise ValueError(f'{name} 必须在 {lower}–{upper} 范围内')
        if type(self.size) is not int or self.size not in SIZES:
            raise ValueError('光标大小必须是 24、32、40、48 或 64')
        if self.appearance not in ('adaptive', 'light', 'dark'):
            raise ValueError('无效的配色策略')
        if self.motion not in MOTIONS:
            raise ValueError('无效的左键动效')
        if self.style not in STYLES:
            raise ValueError('无效的光标几何形态')
        for flag in ('startup', 'aura_glow', 'shake_to_find', 'game_dnd', 'tray_enabled', 'auto_check_update'):
            if type(getattr(self, flag)) is not bool:
                raise ValueError(f'{flag} 必须是布尔值')
        if not isinstance(self.skip_update_version, str):
            raise ValueError('skip_update_version 必须是字符串')
        for name in ('light_body', 'light_outline', 'dark_body', 'dark_outline', 'aura_color'):
            value = getattr(self, name)
            if not isinstance(value, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', value):
                raise ValueError(f'{name} 必须是六位十六进制颜色')
            object.__setattr__(self, name, value.lower())

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ValueError('配置必须是 JSON 对象')
        if 'schema_version' not in value:
            raise ValueError('缺少配置格式版本')
        unknown = set(value) - {field.name for field in fields(cls)}
        if unknown:
            raise ValueError('未知配置项：' + ', '.join(sorted(unknown)))
        return cls(**value)

    def to_dict(self):
        return asdict(self)


def _read_json(path, max_bytes=MAX_JSON_BYTES):
    with Path(path).open('rb') as source:
        content = source.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise ValueError(f'配置文件不能超过 {max_bytes // 1024} KiB')
    try:
        return json.loads(content.decode('utf-8-sig'))
    except (UnicodeError, ValueError) as error:
        raise ValueError('无法读取配置文件，请检查 JSON 格式') from error


def _write_json(path, value):
    content = (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    _write_bytes(path, content)


def _write_bytes(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f'{path.name}.{uuid.uuid4().hex}.tmp')
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class SettingsStore:
    def __init__(self, root):
        self.root = Path(root)
        self.path = self.root / 'settings.json'

    def load(self, legacy_mode_path=None, startup_enabled=False):
        if self.path.exists():
            return CursorSettings.from_dict(_read_json(self.path))
        from .motion import read_mode
        legacy = Path(legacy_mode_path) if legacy_mode_path else self.root / 'click-motion-settings.json'
        settings = CursorSettings(motion=read_mode(legacy), startup=startup_enabled)
        self.save(settings)
        return settings

    def save(self, settings):
        value = CursorSettings.from_dict(settings.to_dict())
        _write_json(self.path, value.to_dict())

    def import_file(self, path):
        raw = _read_json(path)
        if isinstance(raw, dict) and raw.get('format') == 'pointertheme':
            if 'settings' not in raw or not isinstance(raw['settings'], dict):
                raise ValueError('主题包损坏：缺少 settings 配置')
            return CursorSettings.from_dict(raw['settings'])
        return CursorSettings.from_dict(raw)

    def export_file(self, path, settings):
        value = CursorSettings.from_dict(settings.to_dict())
        _write_json(path, value.to_dict())

    def export_theme(self, path, settings, name="Pointer Theme", author="User", desc=""):
        value = CursorSettings.from_dict(settings.to_dict())
        import time
        package = {
            "format": "pointertheme",
            "version": 1,
            "metadata": {
                "name": name,
                "author": author,
                "created": time.strftime("%Y-%m-%d %H:%M:%S"),
                "description": desc,
            },
            "settings": value.to_dict(),
        }
        _write_json(path, package)

    def import_theme(self, path):
        raw = _read_json(path, max_bytes=262144)
        if not isinstance(raw, dict) or raw.get('format') != 'pointertheme':
            # Allow fallback to plain settings JSON
            if isinstance(raw, dict) and 'schema_version' in raw:
                return CursorSettings.from_dict(raw), {"name": "Imported Theme", "author": "", "description": ""}
            raise ValueError('无效的 Pointer 主题包格式')
        settings_dict = raw.get('settings')
        if not isinstance(settings_dict, dict):
            raise ValueError('主题包缺少配置数据')
        metadata = raw.get('metadata') if isinstance(raw.get('metadata'), dict) else {}
        return CursorSettings.from_dict(settings_dict), metadata

