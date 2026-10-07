"""Build a complete Windows release from a private-data-free file list."""

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def clean_build_environment():
    environment=os.environ.copy()
    windows=Path(environment.get('SystemRoot',r'C:\Windows'))
    environment['PATH']=os.pathsep.join(str(path) for path in
        (Path(sys.executable).parent,Path(sys.base_prefix),windows/'System32',windows))
    return environment


def parse_version(version):
    part = r'(0|[1-9]\d*)'
    if not re.fullmatch(part + r'\.' + part + r'\.' + part + r'(?:-beta\.[1-9]\d*)?',version):
        raise ValueError('Invalid semantic release version')
    numeric = tuple(int(value) for value in version.split('-')[0].split('.')) + (0,)
    if max(numeric)>65535:
        raise ValueError('Windows version components exceed 65535')
    return numeric, version


def verify_executable_icon(executable, icon_path):
    """Reject releases whose default PE icon omits the accepted artwork."""
    import pefile  # Already supplied by the builder's PyInstaller dependency.
    source = Path(icon_path).read_bytes()
    reserved, kind, count = struct.unpack_from('<HHH', source)
    if reserved or kind != 1 or not count or len(source) < 6 + 16 * count:
        raise ValueError('Invalid release ICO directory')
    expected = {}
    for index in range(count):
        width, height, _, _, _, _, size, offset = struct.unpack_from('<BBBBHHII', source, 6 + 16 * index)
        if offset < 6 + 16 * count or offset + size > len(source):
            raise ValueError('Invalid release ICO image')
        expected[(width or 256, height or 256)] = hashlib.sha256(source[offset:offset + size]).digest()
    required = {(n, n) for n in (16, 24, 32, 48, 64, 128, 256)}
    if set(expected) != required:
        raise ValueError('Release ICO must include all seven shell and high-DPI sizes')
    pe = pefile.PE(str(executable))
    try:
        icons, group = {}, None
        resources = getattr(pe, 'DIRECTORY_ENTRY_RESOURCE', None)
        for entry in resources.entries if resources else ():
            if entry.id not in (3, 14):
                continue
            for resource in entry.directory.entries:
                data = resource.directory.entries[0].data.struct
                body = pe.get_data(data.OffsetToData, data.Size)
                if entry.id == 3:
                    icons[resource.id] = hashlib.sha256(body).digest()
                elif group is None:
                    group = body
        actual = {}
        if group and len(group) >= 6:
            group_count = struct.unpack_from('<H', group, 4)[0]
            if len(group) == 6 + 14 * group_count:
                for index in range(group_count):
                    width, height, _, _, _, _, _, identity = struct.unpack_from('<BBBBHHIH', group, 6 + 14 * index)
                    actual[(width or 256, height or 256)] = icons.get(identity)
        if actual != expected:
            raise ValueError('Default executable icon does not contain the accepted artwork at every size')
    finally:
        pe.close()
    return sorted(width for width, _ in expected)


def build_release(version, compiler=None, skip_installer=False, output_root=None):
    version_tuple, version = parse_version(version)
    if version != (ROOT / "VERSION").read_text().strip():
        raise ValueError("Update VERSION before building a different version")
    destination = ROOT if output_root is None else Path(output_root).resolve()
    if not destination.is_relative_to(ROOT.resolve()):
        raise ValueError('Build outputs must remain inside the Pointer project')
    if output_root is not None and not skip_installer:
        raise ValueError('Isolated candidate builds must skip the installer')
    build_dir, dist_dir = destination / 'build', destination / 'dist'
    version_file = build_dir / "version-info.txt"
    version_file.parent.mkdir(parents=True, exist_ok=True)
    version_file.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={version_tuple!r}, prodvers={version_tuple!r},
    mask=0x3f, flags=0, OS=0x40004, fileType=0x1, subtype=0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'ReactionForge'),
    StringStruct('FileDescription', 'Pointer Adaptive Cursor'),
    StringStruct('FileVersion', '{version}'),
    StringStruct('InternalName', 'Pointer'),
    StringStruct('OriginalFilename', 'Pointer.exe'),
    StringStruct('ProductName', 'Pointer'),
    StringStruct('ProductVersion', '{version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
""", encoding="utf-8")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", '--clean', "--windowed", "--onedir",
                    '--icon',str(ROOT/'packaging/windows/pointer.ico'),
                    '--runtime-hook',str(ROOT/'packaging/windows/headless_runtime.py'),
                    '--exclude-module','PySide6.QtQml','--exclude-module','PySide6.QtQuick',
                    '--exclude-module','PySide6.QtWebEngineCore','--exclude-module','PySide6.QtTest',
                    "--version-file", str(version_file),
                    "--name", "Pointer", "--distpath", str(dist_dir),
                    "--workpath", str(build_dir), "--specpath", str(build_dir),
                    "--paths", str(ROOT / "src"),
                    str(ROOT / "packaging" / "windows" / "entrypoint.py")], cwd=ROOT, check=True,env=clean_build_environment())
    output = dist_dir / "Pointer"
    verify_executable_icon(output / 'Pointer.exe', ROOT / 'packaging/windows/pointer.ico')
    # Compile on the builder; downloaded clients never require csc or sources.
    from pointer.windows.composition_host import prepare_helper, BUNDLED_HELPER
    helper = prepare_helper(build_dir / 'composition-cache')
    helper_target = output / BUNDLED_HELPER
    helper_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(helper, helper_target)
    # Qt Widgets uses the Windows platform and native style, not browser/QML plugins.
    plugins = output/'_internal/PySide6/plugins'
    if plugins.exists():
        for directory in plugins.iterdir():
            if directory.is_dir() and directory.name not in ('platforms','styles'):
                shutil.rmtree(directory)
        for path in (plugins/'platforms').glob('*.dll'):
            if path.name not in ('qwindows.dll','qoffscreen.dll'):
                path.unlink()
    for filename in ('opengl32sw.dll','Qt6Svg.dll'):
        (output/'_internal/PySide6'/filename).unlink(missing_ok=True)
    for theme in ("adaptive", "reference"):
        shutil.copytree(ROOT / "assets" / "cursors" / theme,
                        output / "assets" / "cursors" / theme, dirs_exist_ok=True)
    shutil.copytree(ROOT / "web" / "cursor-test", output / "web" / "cursor-test", dirs_exist_ok=True)
    shutil.copy2(ROOT / "VERSION", output / "VERSION")
    shutil.copy2(ROOT/'packaging/windows/pointer.ico',output/'pointer.ico')
    shutil.copy2(ROOT / "packaging" / "windows" / "README.txt", output / "使用说明.txt")
    notices = output / "licenses"
    notices.mkdir(exist_ok=True)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise FileNotFoundError("The Python runtime license must accompany the release")
    shutil.copy2(python_license, notices / "Python-LICENSE.txt")
    for name in ('pyinstaller','pillow','pyside6-essentials','shiboken6'):
        distribution = importlib.metadata.distribution(name)
        for resource in distribution.files or []:
            if '.dist-info/licenses/' in resource.as_posix():
                shutil.copy2(distribution.locate_file(resource),notices/(name+'-'+resource.name))
    for resource in (ROOT/'packaging/windows/licenses').iterdir():
        shutil.copy2(resource,notices/resource.name)
    actions = {"一键安装.cmd": "install", "install.cmd": "install",
               "恢复原光标.cmd": "restore", "restore.cmd": "restore",
               "停止自动切换.cmd": "stop", "stop.cmd": "stop",
               "启用自适应.cmd": "apply", "打开测试页.cmd": "test-page",
               "使用倾斜动效.cmd": "tilt", "使用缩小回弹.cmd": "shrink"}
    for filename, action in actions.items():
        (output / filename).write_text(f'@echo off\nstart "" /wait "%~dp0Pointer.exe" --{action}\n',
                                      encoding="utf-8", newline="\r\n")
    files = {path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in sorted(output.rglob("*")) if path.is_file() and path.name != "PACKAGE.json"}
    (output / "PACKAGE.json").write_text(json.dumps({"version": version, "files": files}, indent=2), encoding="utf-8")
    archive = dist_dir / f"Pointer-v{version}-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                package.write(path, "Pointer/" + path.relative_to(output).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    result={'archive':str(archive),'sha256':digest,'files':len(files)}
    if not skip_installer:
        compiler = Path(compiler or r'C:\Program Files (x86)\Inno Setup 6\ISCC.exe')
        if not compiler.is_file():
            raise FileNotFoundError('Inno Setup compiler missing; use GitHub Windows build or --compiler')
        subprocess.run([str(compiler),f'/DAppVersion={version}',str(ROOT/'packaging/windows/installer.iss')],check=True,cwd=ROOT)
        installer=ROOT/'dist'/f'Pointer-v{version}-setup-x64.exe'
        installer_digest=hashlib.sha256(installer.read_bytes()).hexdigest()
        installer.with_suffix('.exe.sha256').write_text(f'{installer_digest}  {installer.name}\n',encoding='ascii')
        result.update(installer=str(installer),installer_sha256=installer_digest)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--version',default=(ROOT/'VERSION').read_text().strip())
    parser.add_argument('--compiler',type=Path)
    parser.add_argument('--skip-installer',action='store_true',help='Developer ZIP build only')
    parser.add_argument('--output-root', type=Path, help='Isolated project output directory; requires --skip-installer')
    args=parser.parse_args()
    print(json.dumps(build_release(args.version,args.compiler,args.skip_installer,args.output_root)))


if __name__ == "__main__":
    main()
