import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


@unittest.skipUnless(os.environ.get('POINTER_PACKAGE_ROOT'),'Set POINTER_PACKAGE_ROOT for isolated packaged checks')
class PackageIntegrationTests(unittest.TestCase):
    def test_packaged_diagnose_install_upgrade_and_uninstall_prepare(self):
        source=Path(os.environ['POINTER_PACKAGE_ROOT']).resolve()
        with tempfile.TemporaryDirectory(prefix='Pointer 安装 验证 ') as folder:
            root=Path(folder);target=root/'app';data=root/'data'
            def run(exe,action):
                report=root/'operation.json'
                report.unlink(missing_ok=True)
                process=subprocess.run([str(exe),action,'--quiet','--report',str(report),
                                        '--install-dir',str(target),'--data-dir',str(data)],
                                       creationflags=0x08000000,timeout=180)
                self.assertEqual(process.returncode,0,report.read_text(encoding='utf-8') if report.exists() else 'missing report')
                return json.loads(report.read_text(encoding='utf-8'))
            diagnostic=run(source/'Pointer.exe','--diagnose')
            self.assertTrue(diagnostic['qt_version'])
            self.assertEqual(diagnostic['cursor_resources'],34)
            self.assertEqual(diagnostic['click_resources'],32)
            self.assertTrue(run(source/'Pointer.exe','--install')['installed'])
            (target/'user-note.txt').write_text('mine')
            self.assertTrue(run(source/'Pointer.exe','--install')['installed'])
            self.assertEqual((target/'user-note.txt').read_text(),'mine')
            original=(data/'settings.json').read_bytes()
            self.assertTrue(run(target/'Pointer.exe','--uninstall')['uninstalled'])
            self.assertEqual((data/'settings.json').read_bytes(),original)
            self.assertTrue((data/'uninstall-owned-files.txt').exists())
            self.assertTrue((target/'Pointer.exe').exists())
            self.assertEqual((target/'user-note.txt').read_text(),'mine')
