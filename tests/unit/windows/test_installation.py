"""Deployment publishes a complete directory and rolls back failed switches."""
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, Mock
from contextlib import ExitStack
from pointer.windows import installation


def package(root,content=b'new'):
    root.mkdir()
    (root/'Pointer.exe').write_bytes(content)
    (root/'VERSION').write_text('1.3.0-beta.1')
    files = {name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('Pointer.exe','VERSION')}
    (root/'PACKAGE.json').write_text(json.dumps({'version':'1.3.0-beta.1','files':files}))


class InstallationTests(unittest.TestCase):
    def test_custom_install_identity_is_written_and_resolved_on_normal_launch(self):
        from pointer.paths import resolve_paths
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';target=root/'Custom Location'
            package(source)
            installation.deploy_package(source,target)
            paths=resolve_paths(target,root/'different AppData',True)
            self.assertEqual(paths.install_root,target)
            self.assertEqual(paths.data_root,root/'data')
            self.assertEqual(resolve_paths(source,root/'AppData',True).install_root,root/'AppData/Pointer/app')

    def test_cached_scheme_locates_verified_previous_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);target=root/'Pointer/app'
            target.parent.mkdir();package(target.parent/'source')
            installation.deploy_package(target.parent/'source',target)
            arrow=root/'Pointer/data/cursor-cache/key/light/adaptive-arrow.cur'
            arrow.parent.mkdir(parents=True);arrow.write_bytes(b'cursor')
            with patch.object(installation.config,'read_values',return_value={'Arrow':{'value':str(arrow)}}):
                self.assertEqual(installation._previous_directory(),target)

    def test_failed_post_deploy_work_recovers_previous_package(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);source=root/'source';target=root/'app'
            package(source);package(target,b'old')
            def resume():
                self.assertEqual((target/'Pointer.exe').read_bytes(),b'new')
                raise RuntimeError('helper failed')
            with self.assertRaisesRegex(RuntimeError,'helper failed'):
                installation.deploy_package(source,target,finalize=resume)
            self.assertEqual((target/'Pointer.exe').read_bytes(),b'old')
            installation.package_files(target)

    def test_failed_upgrade_resume_restores_old_files_preferences_and_service(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root=Path(folder);source=root/'source';target=root/'app';data=root/'data'
            package(source);package(target,b'old');data.mkdir()
            (data/'settings.json').write_bytes(b'{"motion":"shrink"}')
            backend=Mock();backend.snapshot.return_value={'running':True}
            stack.enter_context(patch('pointer.windows.backend.WindowsBackend',return_value=backend))
            for name,value in (('ROOT',source),('INSTALL_ROOT',target),('DATA_ROOT',data),('FROZEN',True)):
                stack.enter_context(patch.object(installation,name,value))
            stack.enter_context(patch.dict(os.environ,{'POINTER_INSTALL_DIR':str(target),'POINTER_DATA_DIR':str(data)}))
            stack.enter_context(patch.object(installation,'_previous_directory',return_value=None))
            stack.enter_context(patch.object(installation,'_migrate_backup'))
            stack.enter_context(patch.object(installation.switcher,'running_directory',return_value=True))
            stack.enter_context(patch.object(installation.switcher,'stop_directory'))
            resumed=[]
            def execute(executable,args,report):
                if '--prepare-upgrade' in args:
                    return {'previously_running':True}
                content=executable.read_bytes();resumed.append(content)
                if content==b'new':
                    (data/'settings.json').write_bytes(b'changed')
                    raise RuntimeError('helper failed')
                return {'running':True}
            stack.enter_context(patch.object(installation,'_execute',side_effect=execute))
            with self.assertRaisesRegex(RuntimeError,'helper failed'):
                installation.install()
            self.assertEqual(resumed,[b'new',b'old'])
            self.assertEqual((target/'Pointer.exe').read_bytes(),b'old')
            self.assertEqual((data/'settings.json').read_bytes(),b'{"motion":"shrink"}')
            backend.restore.assert_called_once()

    def test_invalid_install_marker_cannot_redirect_data(self):
        from pointer.paths import resolve_paths
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            (root/'INSTALLATION.json').write_text('{"schema_version":1,"data_directory":"../../elsewhere"}')
            with self.assertRaisesRegex(ValueError,'安装标识'):
                resolve_paths(root,root/'AppData',True)

    def test_missing_backup_aborts_uninstall_of_active_cached_scheme(self):
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root=Path(folder);target=root/'app';data=root/'data'
            package(target);data.mkdir()
            backend=Mock();backend.backup=data/'missing.json'
            application=Mock(backend=backend)
            stack.enter_context(patch('pointer.application.Application',return_value=application))
            stack.enter_context(patch('pointer.windows.gui_ipc.prepare_gui_upgrade'))
            stack.enter_context(patch.object(installation,'ROOT',target))
            stack.enter_context(patch.object(installation,'INSTALL_ROOT',target))
            stack.enter_context(patch.object(installation,'DATA_ROOT',data))
            stack.enter_context(patch.object(installation.config,'read_values',return_value={'Arrow':{'value':str(data/'cursor-cache/key/light/adaptive-arrow.cur')}}))
            with self.assertRaisesRegex(ValueError,'备份缺失'):
                installation.uninstall()
            backend.stop.assert_not_called();backend.set_startup.assert_not_called()

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
