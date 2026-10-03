"""Install, upgrade and uninstall the built EXE in an isolated directory."""
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    version=(ROOT/'VERSION').read_text().strip()
    installer=ROOT/'dist'/f'Pointer-v{version}-setup-x64.exe'
    with tempfile.TemporaryDirectory(prefix='Pointer 安装包 验证 ') as folder:
        root=Path(folder);target=root/'app';data=root/'data'
        def install():
            completed=subprocess.run([str(installer),'/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-',
                                       '/DIR='+str(target),'/LOG='+str(root/'install.log')],
                                      creationflags=0x08000000,timeout=180)
            if completed.returncode:
                raise RuntimeError('Installer failed: '+str(completed.returncode))
        install()
        if not (target/'Pointer.exe').exists() or not (target/'unins000.exe').exists():
            raise AssertionError('Missing app or registered uninstaller')
        (target/'user-note.txt').write_text('mine')
        data.mkdir(exist_ok=True)
        preferences={'schema_version':1,'motion':'shrink','startup':False}
        (data/'settings.json').write_text(json.dumps(preferences))
        before=(data/'settings.json').read_bytes()
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
        print('installer clean install, preferences-preserving upgrade, uninstall and user files passed')


if __name__=='__main__':
    main()
