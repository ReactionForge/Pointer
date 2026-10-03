"""Deployment publishes a complete directory and rolls back failed switches."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pointer.windows import installation


def package(root,content=b'new'):
    root.mkdir()
    (root/'Pointer.exe').write_bytes(content)
    (root/'VERSION').write_text('1.3.0-beta.1')
    files = {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('Pointer.exe','VERSION')}
    (root/'PACKAGE.json').write_text(json.dumps({'version':'1.3.0-beta.1','files':files}))


class InstallationTests(unittest.TestCase):
    def test_publish_preserves_user_files_and_data(self):
        self.assertTrue(hasattr(installation,'deploy_package'),'Transactional deploy missing')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';target=root/'app';data=root/'data'
            package(source);package(target,b'old');data.mkdir()
            (target/'user-note.txt').write_text('mine')
            (data/'backup.json').write_bytes(b'original')
            installation.deploy_package(source,target)
            self.assertEqual((target/'Pointer.exe').read_bytes(),b'new')
            self.assertEqual((target/'user-note.txt').read_text(),'mine')
            self.assertEqual((data/'backup.json').read_bytes(),b'original')

    def test_failed_directory_switch_restores_complete_previous_package(self):
        self.assertTrue(hasattr(installation,'deploy_package'),'Transactional deploy missing')
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';target=root/'app'
            package(source);package(target,b'old')
            original=installation.os.replace
            def fail_publish(src,dst):
                if Path(src).name.startswith('.pointer-stage-'):
                    raise PermissionError('locked')
                return original(src,dst)
            with patch.object(installation.os,'replace',side_effect=fail_publish):
                with self.assertRaisesRegex(PermissionError,'locked'):
                    installation.deploy_package(source,target)
            self.assertEqual((target/'Pointer.exe').read_bytes(),b'old')
            installation.package_files(target)
