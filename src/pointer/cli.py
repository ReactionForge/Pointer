"""Provide packaged installation, recovery, and background entry points.

Resources live beside the EXE. Backups live outside that folder so installing a
new release cannot replace the settings needed to restore the original cursor.
"""

import argparse
import ctypes
import io
import json
import os
from pathlib import Path
import sys

from pointer.windows import engine as switcher
from pointer.windows import scheme as config
from pointer.windows.installation import package_files, install
from pointer.cursor.theme import THEME_NAME, theme_paths, click_paths
from pointer.paths import DATA_ROOT, FROZEN, INSTALL_ROOT, ROOT




def diagnose():
    switcher._set_dpi_awareness()
    files = package_files(ROOT) if FROZEN else {}
    qt_version = None
    helper_name = None
    gui_shell = None
    if FROZEN:
        for name in ('_internal/PySide6/plugins/platforms/qwindows.dll','licenses/LGPL-3.0.txt','licenses/Python-LICENSE.txt'):
            if not (ROOT/name).is_file():
                raise FileNotFoundError(name)
        from PySide6.QtCore import qVersion
        qt_version = qVersion()
        from pointer.windows.composition_host import bundled_helper, BUNDLED_HELPER
        bundled_helper(ROOT)
        helper_name = BUNDLED_HELPER
        from pointer.ui.material_workspace import MaterialWindow
        gui_shell = MaterialWindow.__name__
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
    click_count = 0
    for mode, theme in ((mode, theme) for mode in ("tilt", "shrink") for theme in ("light", "dark")):
        for frame in range(1, 5):
            for path in click_paths(theme, frame, mode).values():
                cursor = switcher._CursorCache._load(path)
                switcher.USER32.DestroyCursor(cursor)
                click_count += 1
    return {"cursor_resources": count, "animated_resources": animated,
            "click_resources": click_count,
            "package_files": len(files), "frozen": FROZEN, 'qt_version':qt_version,
            'composition_helper': helper_name, 'gui_shell': gui_shell}


def _application():
    from pointer.application import Application
    return Application(DATA_ROOT,INSTALL_ROOT)


def apply_theme(settings=None, *, preserve_runtime=False):
    application = _application()
    return application.apply(settings or application.settings(), preserve_runtime=preserve_runtime)


def stop_theme():
    return _application().pause()


def set_click_mode(mode):
    from dataclasses import replace
    application = _application()
    return application.apply(replace(application.settings(),motion=mode))


def reference_theme():
    from dataclasses import replace
    application = _application()
    return application.apply(replace(application.settings(),appearance='light',motion='off'))


def restore_theme():
    return _application().restore()


def dispatch(action):
    """Downloaded control buttons always operate on the installed helper."""
    if action in ('gui', 'test_page'):
        from pointer.ui.main_window import launch
        return {'exit_code': launch(test_page=action == 'test_page')}
    if action in ('prepare_upgrade', 'uninstall'):
        from pointer.application import Application
        application = Application(DATA_ROOT, INSTALL_ROOT)
        if action == 'prepare_upgrade':
            return application.prepare_upgrade()
        from pointer.windows.installation import uninstall
        return uninstall()
    if action in ("tilt", "shrink"):
        return set_click_mode(action)
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
    for action in ("install", "apply", "stop", "restore", "reference", "run", "diagnose", "test-page", "tilt", "shrink", 'gui', 'prepare-upgrade', 'uninstall'):
        group.add_argument("--" + action, action="store_true")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--report", type=Path)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--install-dir', type=Path)
    parser.add_argument('--settings-file', type=Path)
    parser.add_argument('--preserve-runtime', action='store_true')
    parser.add_argument('--purge-settings', action='store_true')
    args = parser.parse_args(argv)
    if args.quiet:
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
    if args.run:
        switcher._run()
        return 0
    action = next((name for name in ("install", "apply", "stop", "restore", "reference", "diagnose", "test_page", "tilt", "shrink", 'gui', 'prepare_upgrade', 'uninstall')
                   if getattr(args, name)), "gui")
    if action in ('gui', 'test_page'):
        from pointer.ui.main_window import launch
        return launch(test_page=action == 'test_page')
    result = {"action": action, "exit_code": 0}
    messages = {"install": "安装完成。打开 Pointer 设置界面，预览并应用你的光标配置。",
                "apply": "自适应光标已启用。", "stop": "已暂停光标效果，开机启动选择保持不变。",
                "restore": "已恢复原来的 Windows 光标。", "reference": "已启用固定黑色主体、灰白边框的原始造型。",
                "diagnose": "发布包和光标资源检查通过。"}
    messages.update(tilt="已启用倾斜动效：按下时箭头整体向左下倾斜、下方轻微跟随，小手向左倾斜，松开回正。",
                    shrink="已启用缩小回弹：按下缩小约 10%，松开恢复。")
    messages.update(prepare_upgrade='已为升级做好准备。', uninstall='原光标已恢复，可以卸载。')
    try:
        if action == 'apply' and (args.settings_file or args.preserve_runtime):
            settings = _application().store.import_file(args.settings_file) if args.settings_file else None
            result.update(apply_theme(settings, preserve_runtime=args.preserve_runtime))
        elif action == 'uninstall':
            from pointer.windows.installation import uninstall
            result.update(uninstall(args.purge_settings))
        else:
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
