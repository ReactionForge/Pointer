"""Install, upgrade and uninstall the built EXE in an isolated directory."""
import base64
import ctypes
from ctypes import wintypes
import json
import ntpath
from pathlib import Path
import subprocess
import shutil
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def read_shortcuts():
    """Read the current user's two existing Pointer links without saving them."""
    script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$paths = @(
    @{kind='desktop'; path=(Join-Path ([Environment]::GetFolderPath('DesktopDirectory')) 'Pointer.lnk')},
    @{kind='start_menu'; path=(Join-Path ([Environment]::GetFolderPath('Programs')) 'Pointer\Pointer.lnk')}
)
$shell = New-Object -ComObject WScript.Shell
$rows = foreach ($item in $paths) {
    if (-not (Test-Path -LiteralPath $item.path -PathType Leaf)) {
        throw ('Missing installed shortcut: ' + $item.path)
    }
    $link = $shell.CreateShortcut($item.path)
    @{kind=$item.kind; path=$item.path; target=$link.TargetPath; icon=$link.IconLocation}
}
ConvertTo-Json -InputObject @($rows) -Compress
"""
    encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
    completed = subprocess.run(
        ['powershell.exe', '-NoLogo', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
        capture_output=True, encoding='utf-8', check=True, timeout=30, creationflags=0x08000000)
    return json.loads(completed.stdout)


def verify_shell_icon(path):
    """Extract and render a link's Shell icon into memory; require visible pixels."""
    class ShellFileInfo(ctypes.Structure):
        _fields_ = [('hIcon', wintypes.HICON), ('iIcon', ctypes.c_int),
                    ('dwAttributes', wintypes.DWORD), ('szDisplayName', wintypes.WCHAR * 260),
                    ('szTypeName', wintypes.WCHAR * 80)]

    class BitmapInfoHeader(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('width', wintypes.LONG), ('height', wintypes.LONG),
                    ('planes', wintypes.WORD), ('bit_count', wintypes.WORD),
                    ('compression', wintypes.DWORD), ('image_size', wintypes.DWORD),
                    ('xppm', wintypes.LONG), ('yppm', wintypes.LONG),
                    ('colors_used', wintypes.DWORD), ('colors_important', wintypes.DWORD)]

    ole = ctypes.WinDLL('ole32', use_last_error=True)
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    user = ctypes.WinDLL('user32', use_last_error=True)
    gdi = ctypes.WinDLL('gdi32', use_last_error=True)

    def signature(library, name, arguments, result):
        function = getattr(library, name)
        function.argtypes, function.restype = arguments, result
        return function

    signature(ole, 'CoInitialize', [ctypes.c_void_p], ctypes.c_long)
    signature(ole, 'CoUninitialize', [], None)
    signature(shell, 'SHGetFileInfoW', [wintypes.LPCWSTR, wintypes.DWORD,
              ctypes.POINTER(ShellFileInfo), wintypes.UINT, wintypes.UINT], ctypes.c_size_t)
    signature(user, 'DrawIconEx', [wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.HICON,
              ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.HBRUSH, wintypes.UINT], wintypes.BOOL)
    signature(user, 'DestroyIcon', [wintypes.HICON], wintypes.BOOL)
    signature(gdi, 'CreateCompatibleDC', [wintypes.HDC], wintypes.HDC)
    signature(gdi, 'CreateDIBSection', [wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
              ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD], wintypes.HBITMAP)
    signature(gdi, 'SelectObject', [wintypes.HDC, wintypes.HANDLE], wintypes.HANDLE)
    signature(gdi, 'GdiFlush', [], wintypes.BOOL)
    signature(gdi, 'DeleteObject', [wintypes.HANDLE], wintypes.BOOL)
    signature(gdi, 'DeleteDC', [wintypes.HDC], wintypes.BOOL)
    initialized = ole.CoInitialize(None)
    # A preexisting COM apartment also satisfies SHGetFileInfo's requirement.
    if initialized < 0 and initialized != -2147417850:  # RPC_E_CHANGED_MODE
        raise OSError('Shell icon COM initialization failed: ' + str(initialized))
    info = ShellFileInfo()
    dc = bitmap = previous = None
    try:
        # No USEFILEATTRIBUTES or LINKOVERLAY: inspect the actual installed link.
        if not shell.SHGetFileInfoW(str(path), 0, ctypes.byref(info), ctypes.sizeof(info), 0x100) or not info.hIcon:
            raise AssertionError('Missing Shell icon: ' + str(path))
        dc = gdi.CreateCompatibleDC(None)
        if not dc:
            raise ctypes.WinError(ctypes.get_last_error())
        size = 32
        header = BitmapInfoHeader(ctypes.sizeof(BitmapInfoHeader), size, -size, 1, 32,
                                  0, size * size * 4, 0, 0, 0, 0)
        bits = ctypes.c_void_p()
        bitmap = gdi.CreateDIBSection(dc, ctypes.byref(header), 0, ctypes.byref(bits), None, 0)
        if not bitmap or not bits.value:
            raise ctypes.WinError(ctypes.get_last_error())
        old = gdi.SelectObject(dc, bitmap)
        if not old or old == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        previous = old
        background = bytes((219, 31, 177, 255))
        pixels = background * (size * size)
        ctypes.memmove(bits, pixels, len(pixels))
        if not user.DrawIconEx(dc, 0, 0, info.hIcon, size, size, 0, None, 3):
            raise ctypes.WinError(ctypes.get_last_error())
        gdi.GdiFlush()
        rendered = ctypes.string_at(bits, len(pixels))
        if not any(rendered[offset:offset + 3] != background[:3] for offset in range(0, len(pixels), 4)):
            raise AssertionError('Empty Shell icon: ' + str(path))
    finally:
        if previous:
            gdi.SelectObject(dc, previous)
        if bitmap:
            gdi.DeleteObject(bitmap)
        if dc:
            gdi.DeleteDC(dc)
        if info.hIcon:
            user.DestroyIcon(info.hIcon)
        if initialized >= 0:
            ole.CoUninitialize()


def verify_shortcuts(target):
    for name in ('Pointer.exe', 'pointer.ico'):
        if not (target / name).is_file():
            raise AssertionError('Missing installed shortcut resource: ' + str(target / name))
    rows = read_shortcuts()
    if not isinstance(rows, list) or len(rows) != 2 or {row.get('kind') for row in rows} != {'desktop', 'start_menu'}:
        raise AssertionError('Missing desktop or Start Menu Pointer shortcut')

    def normalized(path):
        return ntpath.normcase(ntpath.normpath(str(Path(path.strip().strip('"')).resolve())))

    executable = normalized(str(target / 'Pointer.exe'))
    icon = normalized(str(target / 'pointer.ico'))
    for row in rows:
        if normalized(row['target']) != executable:
            raise AssertionError('Shortcut targets a different installation: ' + json.dumps({
                'shortcut': row['path'], 'actual': row['target'], 'expected': executable}, ensure_ascii=True))
        location, separator, index = row['icon'].rpartition(',')
        if not separator or index.strip() != '0' or normalized(location) != icon:
            raise AssertionError('Shortcut does not use the installed pointer.ico,0: ' + json.dumps({
                'shortcut': row['path'], 'actual': row['icon'], 'expected': icon + ',0'}, ensure_ascii=True))
    for row in rows:
        verify_shell_icon(Path(row['path']))
    return rows


def main():
    version=(ROOT/'VERSION').read_text().strip()
    installer=ROOT/'dist'/f'Pointer-v{version}-setup-x64.exe'
    with tempfile.TemporaryDirectory(prefix='Pointer 安装包 验证 ') as folder:
        root=Path(folder);target=root/'Pointer 自定义安装';data=root/'data'
        reports=ROOT/'.local/reports';reports.mkdir(parents=True,exist_ok=True)
        def install():
            completed=subprocess.run([str(installer),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',
                                       '/TASKS=desktopicon',
                                       '/DIR='+str(target),'/LOG='+str(root/'install.log')],
                                      creationflags=0x08000000,timeout=180)
            # Preserve the real installer log even when a following check fails.
            if (root/'install.log').is_file():
                shutil.copy2(root/'install.log',reports/'installer-smoke.log')
            if completed.returncode:
                raise RuntimeError('Installer failed: '+str(completed.returncode))
            rows = verify_shortcuts(target)
            print('installed shortcut targets, icon locations and Shell pixels passed: ' +
                  json.dumps(rows))
        install()
        if not (target/'Pointer.exe').exists() or not (target/'unins000.exe').exists():
            raise AssertionError('Missing app or registered uninstaller')
        (target/'user-note.txt').write_text('mine')
        data.mkdir(exist_ok=True)
        preferences={'schema_version':1,'motion':'shrink','startup':False}
        (data/'settings.json').write_text(json.dumps(preferences))
        before=(data/'settings.json').read_bytes()
        report=root/'normal-launch.json'
        completed=subprocess.run([str(target/'Pointer.exe'),'--prepare-upgrade','--quiet','--report',str(report)],
                                 creationflags=0x08000000,timeout=30)
        assert completed.returncode==0,json.loads(report.read_text(encoding='utf-8'))
        assert (data/'upgrade-state.json').exists(),'Normal launch lost custom installation data'
        install()
        assert (data/'settings.json').read_bytes()==before
        assert (target/'user-note.txt').read_text()=='mine'
        completed=subprocess.run([str(target/'unins000.exe'),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART'],
                                 creationflags=0x08000000,timeout=180)
        if completed.returncode:
            raise RuntimeError('Uninstaller failed: '+str(completed.returncode))
        assert not (target/'Pointer.exe').exists()
        assert (target/'user-note.txt').read_text()=='mine'
        assert (data/'settings.json').read_bytes()==before
        reports=ROOT/'.local/reports';reports.mkdir(parents=True,exist_ok=True)
        shutil.copy2(root/'install.log',reports/'installer-smoke.log')
        print('installer clean install, shortcut icons, preferences-preserving upgrade, uninstall and user files passed')


if __name__=='__main__':
    main()
