"""Build a complete Windows release from a private-data-free file list."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default=(ROOT / "VERSION").read_text().strip())
    args = parser.parse_args()
    if not re.fullmatch(r"\d+\.\d+\.\d+", args.version):
        raise ValueError("Use a semantic version, for example 1.0.0")
    if args.version != (ROOT / "VERSION").read_text().strip():
        raise ValueError("Update VERSION before building a different version")
    version_file = ROOT / "build" / "version-info.txt"
    version_file.parent.mkdir(exist_ok=True)
    version_tuple = tuple(int(part) for part in args.version.split(".")) + (0,)
    version_file.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={version_tuple!r}, prodvers={version_tuple!r},
    mask=0x3f, flags=0, OS=0x40004, fileType=0x1, subtype=0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'ReactionForge'),
    StringStruct('FileDescription', 'Pointer Adaptive Cursor'),
    StringStruct('FileVersion', '{args.version}'),
    StringStruct('InternalName', 'Pointer'),
    StringStruct('OriginalFilename', 'Pointer.exe'),
    StringStruct('ProductName', 'Pointer'),
    StringStruct('ProductVersion', '{args.version}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
""", encoding="utf-8")
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed", "--onedir",
                    "--version-file", str(version_file),
                    "--name", "Pointer", "--distpath", str(ROOT / "dist"),
                    "--workpath", str(ROOT / "build"), "--specpath", str(ROOT / "build"),
                    "--paths", str(ROOT / "src"),
                    str(ROOT / "packaging" / "windows" / "entrypoint.py")], cwd=ROOT, check=True)
    output = ROOT / "dist" / "Pointer"
    for theme in ("adaptive", "reference"):
        shutil.copytree(ROOT / "assets" / "cursors" / theme,
                        output / "assets" / "cursors" / theme, dirs_exist_ok=True)
    shutil.copytree(ROOT / "web" / "cursor-test", output / "web" / "cursor-test", dirs_exist_ok=True)
    shutil.copy2(ROOT / "VERSION", output / "VERSION")
    shutil.copy2(ROOT / "packaging" / "windows" / "README.txt", output / "使用说明.txt")
    notices = output / "licenses"
    notices.mkdir(exist_ok=True)
    python_license = Path(sys.base_prefix) / "LICENSE.txt"
    if not python_license.is_file():
        raise FileNotFoundError("The Python runtime license must accompany the release")
    shutil.copy2(python_license, notices / "Python-LICENSE.txt")
    distribution = importlib.metadata.distribution("pyinstaller")
    for resource in distribution.files or []:
        if ".dist-info/licenses/" in resource.as_posix():
            shutil.copy2(distribution.locate_file(resource), notices / ("PyInstaller-" + resource.name))
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
    (output / "PACKAGE.json").write_text(json.dumps({"version": args.version, "files": files}, indent=2), encoding="utf-8")
    archive = ROOT / "dist" / f"Pointer-v{args.version}-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as package:
        for path in sorted(output.rglob("*")):
            if path.is_file():
                package.write(path, "Pointer/" + path.relative_to(output).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix(".zip.sha256").write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    print(json.dumps({"archive": str(archive), "sha256": digest, "files": len(files)}))


if __name__ == "__main__":
    main()
