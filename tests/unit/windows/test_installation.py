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
    def test_portable_apply_forwards_runtime_intent_without_reinstall(self):
        from pointer.cursor.settings import CursorSettings
        with tempfile.TemporaryDirectory() as folder, ExitStack() as stack:
            root = Path(folder)
            source, target, data = root/'source', root/'app', root/'data'
            package(source)
            package(target)
            data.mkdir()
            for name, value in (('ROOT', source), ('INSTALL_ROOT', target), ('DATA_ROOT', data)):
                stack.enter_context(patch.object(installation, name, value))
            install = stack.enter_context(patch.object(installation, 'install'))
            execute = stack.enter_context(patch.object(installation, '_execute', return_value={'running': False}))
            for preserve in (True, False):
                installation.apply_portable(CursorSettings(), preserve_runtime=preserve)
                arguments = execute.call_args.args[1]
                self.assertEqual('--preserve-runtime' in arguments, preserve)
                self.assertIn('--settings-file', arguments)
                self.assertEqual(list(data.iterdir()), [])
            install.assert_not_called()

    def test_custom_install_identity_is_written_and_resolved_on_normal_launch(self):
        from pointer.paths import resolve_paths
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();source=root/'source';target=root/'Custom Location'
            package(source)
            installation.deploy_package(source,target)
            paths=resolve_paths(target,root/'different AppData',True)
            self.assertEqual(paths.install_root,target)
            self.assertEqual(paths.data_root,root/'data')
            self.assertEqual(resolve_paths(source,root/'AppData',True).install_root,root/'AppData/Pointer/app')

    def test_cached_scheme_locates_verified_previous_installation(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();target=root/'Pointer/app'
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
            stack.enter_context(patch('pointer.windows.gui_ipc.prepare_gui_upgrade'))
            stack.enter_context(patch('pointer.windows.backend.WindowsBackend',return_value=backend))
            for name,value in (('ROOT',source),('INSTALL_ROOT',target),('DATA_ROOT',data),('FROZEN',True)):
                stack.enter_context(patch.object(installation,name,value))
            stack.enter_context(patch.dict(os.environ,{'POINTER_INSTALL_DIR':str(target),'POINTER_DATA_DIR':str(data)}))
            stack.enter_context(patch.object(installation,'_previous_directory',return_value=None))
            stack.enter_context(patch.object(installation,'_migrate_backup'))
            stack.enter_context(patch.object(installation.switcher,'running_directory',return_value=True))
            stack.enter_context(patch.object(installation.switcher,'stop_directory'))
            resumed=[]
            def execute(executable,args,report, *, upgrade_resume=False):
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
            root=Path(folder).resolve();target=root/'app';data=root/'data'
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

    def test_failed_switch_and_restore_keep_both_errors_and_old_package(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source, target = root/'source', root/'app'
            package(source)
            package(target, b'old')
            original = installation.os.replace
            def fail_switch_or_restore(source, destination):
                if Path(source).name.startswith('.pointer-stage-'):
                    raise PermissionError('publish failed')
                if Path(source).name.startswith('.pointer-rollback-'):
                    raise OSError('restore failed')
                return original(source, destination)
            with patch.object(installation.os, 'replace', side_effect=fail_switch_or_restore):
                with self.assertRaisesRegex(RuntimeError, 'publish failed.*restore failed') as caught:
                    installation.deploy_package(source, target)
            self.assertIsInstance(caught.exception.__cause__, PermissionError)
            old = list(root.glob('.pointer-rollback-*/Pointer.exe'))
            self.assertEqual(len(old), 1)
            self.assertEqual(old[0].read_bytes(), b'old')

    def test_execute_rejects_stale_success_report(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder)/'report.json'
            report.write_text('{"exit_code":0,"running":true}')
            with patch.object(installation.subprocess, 'run', return_value=Mock(returncode=0)):
                with self.assertRaisesRegex(RuntimeError, '未成功完成'):
                    installation._execute(Path(folder)/'Pointer.exe', ['--apply'], report)
            self.assertFalse(report.exists())

    def test_execute_scopes_upgrade_marker_without_changing_legacy_arguments(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            executable, report = root/'Pointer.exe', root/'report.json'
            arguments = ['--apply', '--install-dir', str(root), '--data-dir', str(root)]
            for internal in (False, True):
                with self.subTest(internal=internal):
                    def child(command, **kwargs):
                        self.assertEqual(command, [str(executable), *arguments, '--quiet', '--report', str(report)])
                        expected = str(root/'upgrade-state.json') if internal else None
                        self.assertEqual(kwargs['env'].get('POINTER_UPGRADE_HANDOFF'), expected)
                        self.assertEqual(kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'], '1')
                        report.write_text(json.dumps({'exit_code': 0, 'running': True}), encoding='utf-8')
                        return Mock(returncode=0)
                    with patch.dict(os.environ, {'POINTER_UPGRADE_HANDOFF': 'stale-parent-marker'}), \
                            patch.object(installation.subprocess, 'run', side_effect=child):
                        self.assertTrue(installation._execute(executable, arguments, report,
                                                             upgrade_resume=internal)['running'])
                        self.assertEqual(os.environ['POINTER_UPGRADE_HANDOFF'], 'stale-parent-marker')

    def test_execute_and_shortcuts_run_silently_without_console_window(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / 'report.json'
            def write_report(*args, **kwargs):
                report.write_text(json.dumps({'exit_code': 0}))
                return Mock(returncode=0)
            with patch.object(installation.subprocess, 'run', side_effect=write_report) as run_mock:
                installation._execute(Path(folder) / 'Pointer.exe', ['--apply'], report)
                run_mock.assert_called_once()
                kwargs = run_mock.call_args.kwargs
                self.assertEqual(kwargs['creationflags'], 0x08000000)
                self.assertEqual(kwargs['stdin'], installation.subprocess.DEVNULL)
                self.assertEqual(kwargs['stdout'], installation.subprocess.DEVNULL)
                self.assertEqual(kwargs['stderr'], installation.subprocess.DEVNULL)
                startupinfo = kwargs.get('startupinfo')
                self.assertIsNotNone(startupinfo)
                self.assertEqual(startupinfo.wShowWindow, 0)

            with patch.dict(os.environ, {'APPDATA': folder}), \
                    patch.object(installation.subprocess, 'run', return_value=Mock(returncode=0)) as run_mock:
                installation._shortcuts()
                run_mock.assert_called_once()
                kwargs = run_mock.call_args.kwargs
                self.assertEqual(kwargs['creationflags'], 0x08000000)
                self.assertEqual(kwargs['stdin'], installation.subprocess.DEVNULL)
                self.assertEqual(kwargs['stdout'], installation.subprocess.DEVNULL)
                self.assertEqual(kwargs['stderr'], installation.subprocess.DEVNULL)
                startupinfo = kwargs.get('startupinfo')
                self.assertIsNotNone(startupinfo)
                self.assertEqual(startupinfo.wShowWindow, 0)


class UpgradeTransactionTests(unittest.TestCase):
    def setUp(self):
        from pointer.cursor.settings import CursorSettings, SettingsStore
        from pointer.windows.backend import WindowsBackend
        self.backend_type = WindowsBackend
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory())).resolve()
        self.source, self.target, self.data = self.root/'source', self.root/'custom-app', self.root/'custom-data'
        package(self.source)
        package(self.target, b'old')
        self.data.mkdir()
        self.settings = CursorSettings(startup=True)
        SettingsStore(self.data).save(self.settings)
        self.backup = self.data/'original-cursor-settings.json'
        self.original_backup = b'{"cursor_values":{"Arrow":{"value":"original","type":1}},"previous_named_scheme":null}'
        self.backup.write_bytes(self.original_backup)
        self.startup_text = json.dumps({'value_name': 'PointerAdaptiveContrast', 'previous': None,
                                        'installed_command': str(self.target/'Pointer.exe')+' --run'})
        (self.data/'contrast-switcher-startup-backup.json').write_text(self.startup_text, encoding='utf-8')
        self.before = {'registry': {'cursor_values': {'Arrow': {'value': str(self.data/'cursor-cache/key/light/adaptive-arrow.cur'), 'type': 1}},
                                   'scheme_name': 'Pointer', 'previous_named_scheme': None},
                       'run': {'value': str(self.target/'Pointer.exe')+' --run', 'type': 1},
                       'startup_backup': self.startup_text, 'startup_enabled': True, 'previous_root': None}
        self.running = True
        self.events = []
        self.backend = Mock()
        self.backend.snapshot.side_effect = lambda: self.events.append('snapshot') or {**self.before, 'running': self.running}
        self.backend.startup_enabled.return_value = True
        self.stack.enter_context(patch('pointer.windows.backend.WindowsBackend', return_value=self.backend))
        for name, value in (('ROOT', self.source), ('INSTALL_ROOT', self.target), ('DATA_ROOT', self.data), ('FROZEN', True)):
            self.stack.enter_context(patch.object(installation, name, value))
        self.stack.enter_context(patch.dict(os.environ, {'LOCALAPPDATA': str(self.root), 'APPDATA': str(self.root),
                                                       'POINTER_INSTALL_DIR': str(self.target), 'POINTER_DATA_DIR': str(self.data)}))
        self.gate = self.stack.enter_context(patch('pointer.windows.gui_ipc.prepare_gui_upgrade', side_effect=lambda: self.events.append('gate')))
        self.stack.enter_context(patch.object(installation, '_previous_directory', return_value=None))
        self.stack.enter_context(patch.object(installation.config, 'BACKUP', self.backup))
        self.migrate = self.stack.enter_context(patch.object(installation, '_migrate_backup'))
        self.stack.enter_context(patch.object(installation.switcher, 'running_directory', side_effect=lambda *a, **kw: self.running))
        self.stop = self.stack.enter_context(patch.object(installation.switcher, 'stop_directory', side_effect=self.stop_runtime))
        self.real_execute = installation._execute
        self.execute = self.stack.enter_context(patch.object(installation, '_execute', side_effect=self.resume_runtime))
        self.stack.enter_context(patch.object(installation, '_shortcuts'))

    def stop_runtime(self, *args, **kwargs):
        self.events.append('stop')
        self.running = False

    def resume_runtime(self, executable, arguments, report, *, upgrade_resume=False):
        self.assertEqual(arguments, ['--apply', '--install-dir', str(self.target), '--data-dir', str(self.data)])
        self.assertEqual(report.parent, self.data)
        self.events.append('resume:'+executable.read_bytes().decode())
        self.running = True
        return {'running': True, 'exit_code': 0}

    def bridge_real_cli(self, command, **kwargs):
        import io
        from pointer import cli
        from pointer.application import Application
        executable = Path(command[0])
        root = Path(command[command.index('--install-dir')+1])
        data = Path(command[command.index('--data-dir')+1])
        report = Path(command[command.index('--report')+1])
        self.assertEqual(command, [str(executable), '--apply', '--install-dir', str(root),
                                   '--data-dir', str(data), '--quiet', '--report', str(report)])
        self.assertEqual(kwargs['env']['POINTER_UPGRADE_HANDOFF'], str(data/'upgrade-state.json'))
        self.events.append('cli:'+executable.read_bytes().decode())
        application = Application(data, root, self.backend)
        with patch.dict(os.environ, kwargs['env'], clear=True), \
                patch.object(cli, '_application', return_value=application), \
                patch.object(cli.sys, 'stdout', io.StringIO()), patch.object(cli.sys, 'stderr', io.StringIO()):
            code = cli.main(command[1:])
            self.assertNotIn('POINTER_UPGRADE_HANDOFF', os.environ)
        return Mock(returncode=code)

    def write_legacy_handoff(self, previous=None):
        # Old prepare_upgrade wrote this real Application/WindowsBackend snapshot
        # verbatim; it did not include directory IDs or a transaction timestamp.
        from pointer.application import Application
        from pointer.windows import backend as boundary
        with patch.object(self.backend_type, 'previous_installation', return_value=previous), \
                patch.object(self.backend_type, 'runtime_status', return_value={}), \
                patch.object(self.backend_type, 'startup_enabled', return_value=True), \
                patch.object(boundary, '_run_value', return_value=self.before['run']), \
                patch.object(boundary.scheme, 'read_values', side_effect=lambda key: self.before['registry']['cursor_values'] if key == boundary.scheme.KEY_PATH else {}):
            payload = Application(self.data, self.target, self.backend_type(self.data, self.target)).snapshot()
        self.before = {key: value for key, value in payload.items() if key not in ('settings', 'running')}
        self.assertNotIn('upgrade_install_root', payload)
        self.assertNotIn('upgrade_data_root', payload)
        path = self.data/'upgrade-state.json'
        path.write_text(json.dumps(payload), encoding='utf-8')
        self.running = False
        self.events.clear()
        self.backend.snapshot.reset_mock()
        return path, payload

    def write_previous_handoff(self):
        previous = self.root/'previous'/'app'
        previous.parent.mkdir()
        package(previous, b'previous')
        (previous.parent/'data').mkdir()
        self.before['registry']['cursor_values']['Arrow']['value'] = str(previous/'assets'/'arrow.cur')
        self.before['run']['value'] = str(previous/'Pointer.exe')+' --run'
        startup = json.loads(self.startup_text)
        startup['installed_command'] = self.before['run']['value']
        self.startup_text = json.dumps(startup)
        (self.data/'contrast-switcher-startup-backup.json').write_text(self.startup_text, encoding='utf-8')
        self.stack.enter_context(patch.object(installation, '_previous_directory', return_value=previous))
        self.stack.enter_context(patch.dict(os.environ, {'POINTER_DATA_DIR': ''}))
        self.startup_enable = self.stack.enter_context(patch('pointer.windows.startup.enable_startup'))
        with patch.object(installation.switcher, 'running_directory', side_effect=lambda root, *a, **kw: root == previous):
            path, payload = self.write_legacy_handoff(previous)
        self.assertFalse(payload['running'])
        self.assertEqual(payload['previous_root'], str(previous))
        self.before['previous_root'] = None
        return previous, path, payload

    def assert_originals(self):
        self.assertEqual(self.backup.read_bytes(), self.original_backup)
        self.assertEqual((self.data/'contrast-switcher-startup-backup.json').read_text(encoding='utf-8'), self.startup_text)
        self.backend.set_startup.assert_not_called()

    def test_direct_cli_install_keeps_first_running_intent_after_stop_refreshes_status(self):
        from pointer import cli
        with patch.object(cli, 'install', installation.install):
            self.assertTrue(cli.dispatch('install')['installed'])
        self.assertEqual(self.events, ['gate', 'snapshot', 'stop', 'resume:new'])
        self.backend.snapshot.assert_called_once()
        self.assertTrue(self.running)
        self.assertEqual((self.target/'Pointer.exe').read_bytes(), b'new')
        self.assert_originals()

    def test_paused_install_remains_paused(self):
        self.running = False
        installation.install()
        self.execute.assert_not_called()
        self.assertFalse(self.running)
        self.assert_originals()

    def test_gui_rejection_precedes_snapshot_stop_and_deploy(self):
        self.gate.side_effect = RuntimeError('busy or dirty draft')
        with self.assertRaisesRegex(RuntimeError, 'busy or dirty draft'):
            installation.install()
        self.backend.snapshot.assert_not_called()
        self.stop.assert_not_called()
        self.execute.assert_not_called()
        self.assertEqual((self.target/'Pointer.exe').read_bytes(), b'old')
        self.assert_originals()

    def test_invalid_source_does_not_close_gui_or_stop(self):
        (self.source/'Pointer.exe').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError, 'checksum'):
            installation.install()
        self.gate.assert_not_called()
        self.stop.assert_not_called()
        self.assert_originals()

    def test_backup_failure_precedes_stop(self):
        self.migrate.side_effect = OSError('backup read failed')
        with self.assertRaisesRegex(OSError, 'backup read failed'):
            installation.install()
        self.stop.assert_not_called()
        self.backend.restore.assert_not_called()
        self.execute.assert_not_called()
        self.assert_originals()

    def test_stop_failure_restores_and_resumes_old_helper(self):
        def fail_stop(*args, **kwargs):
            self.running = False
            raise RuntimeError('stop failed')
        self.stop.side_effect = fail_stop
        with self.assertRaisesRegex(RuntimeError, 'stop failed'):
            installation.install()
        self.backend.restore.assert_called_once_with({**self.before, 'running': False, 'previous_root': None})
        self.assertEqual(self.events[-1], 'resume:old')
        self.assertTrue(self.running)
        self.assert_originals()

    def test_copy_failure_recovers_old_package_and_runtime(self):
        real_copy = installation.shutil.copy2
        def fail_new_copy(source, target, *args, **kwargs):
            if Path(source) == self.source/'Pointer.exe':
                raise OSError('copy failed')
            return real_copy(source, target, *args, **kwargs)
        with patch.object(installation.shutil, 'copy2', side_effect=fail_new_copy):
            with self.assertRaisesRegex(OSError, 'copy failed'):
                installation.install()
        self.assertEqual((self.target/'Pointer.exe').read_bytes(), b'old')
        self.assertEqual(self.events[-1], 'resume:old')
        self.assert_originals()

    def test_resume_failure_restores_files_and_old_runtime(self):
        settings_before = (self.data/'settings.json').read_bytes()
        def fail_new_resume(executable, arguments, report, *, upgrade_resume=False):
            if executable.read_bytes() == b'new':
                (self.data/'settings.json').write_bytes(b'changed')
                self.backup.write_bytes(b'changed backup')
                raise RuntimeError('new helper failed')
            return self.resume_runtime(executable, arguments, report)
        self.execute.side_effect = fail_new_resume
        with self.assertRaisesRegex(RuntimeError, 'new helper failed'):
            installation.install()
        self.assertEqual((self.data/'settings.json').read_bytes(), settings_before)
        self.assertEqual((self.target/'Pointer.exe').read_bytes(), b'old')
        self.assertTrue(self.running)
        self.assert_originals()

    def test_recovery_failure_keeps_primary_error_and_cause(self):
        original = RuntimeError('deployment failed')
        self.backend.restore.side_effect = OSError('registry restore failed')
        with patch.object(installation, 'deploy_package', side_effect=original):
            with self.assertRaisesRegex(RuntimeError, 'deployment failed.*registry restore failed') as caught:
                installation.install()
        self.assertIs(caught.exception.__cause__, original)
        self.execute.assert_not_called()
        self.assert_originals()

    def test_first_original_backup_survives_failed_install(self):
        self.backup.unlink()
        def create_first_backup(executable, arguments, report, *, upgrade_resume=False):
            if executable.read_bytes() == b'new':
                self.backup.write_bytes(self.original_backup)
                raise RuntimeError('start failed after backup')
            return self.resume_runtime(executable, arguments, report)
        self.execute.side_effect = create_first_backup
        with self.assertRaisesRegex(RuntimeError, 'start failed after backup'):
            installation.install()
        self.assert_originals()

    def test_real_legacy_snapshot_resumes_running_intent_and_is_consumed(self):
        path, payload = self.write_legacy_handoff()
        self.assertTrue(payload['running'])
        installation.install()
        self.assertEqual(self.events, ['gate', 'snapshot', 'stop', 'resume:new'])
        self.assertFalse(path.exists())
        self.assert_originals()

    def test_user_pause_invalidates_handoff_before_delayed_install(self):
        from pointer.application import Application
        path, _ = self.write_legacy_handoff()
        self.backend.stop.side_effect = self.stop_runtime
        Application(self.data, self.target, self.backend).pause()
        self.assertFalse(path.exists())
        self.events.clear()
        installation.install()
        self.execute.assert_not_called()
        self.assertFalse(self.running)
        self.assertEqual(self.events, ['gate', 'snapshot', 'stop'])
        self.assert_originals()

    def test_legacy_settings_compare_semantically_after_default_and_color_normalization(self):
        for raw in ({'schema_version': 1, 'startup': True},
                    {**self.settings.to_dict(), 'dark_body': '#FFFFFF', 'aura_color': '#007AFF'}):
            with self.subTest(raw=raw):
                (self.data/'settings.json').write_text(json.dumps(raw), encoding='utf-8')
                self.running = True
                path, payload = self.write_legacy_handoff()
                self.assertNotEqual(payload['settings'], raw)
                self.execute.reset_mock()
                installation.install()
                self.execute.assert_called_once()
                self.assertFalse(path.exists())
                self.assertTrue(self.running)
                self.assert_originals()

    def test_previous_handoff_resumes_new_target_after_success(self):
        previous, path, _ = self.write_previous_handoff()
        installation.install()
        self.assertEqual(self.events, ['gate', 'snapshot', 'stop', 'stop', 'resume:new'])
        self.assertEqual(self.execute.call_args.args[0], self.target/'Pointer.exe')
        self.assertTrue(self.running)
        self.assertFalse(path.exists())
        self.assertEqual((previous/'Pointer.exe').read_bytes(), b'previous')
        self.startup_enable.assert_called_once_with()
        self.assert_originals()

    def test_previous_handoff_resumes_only_previous_directory_after_deploy_failure(self):
        previous, path, _ = self.write_previous_handoff()
        self.execute.side_effect = None
        self.execute.return_value = {'running': True}
        with patch.object(installation, 'deploy_package', side_effect=RuntimeError('deploy failed')):
            with self.assertRaisesRegex(RuntimeError, 'deploy failed'):
                installation.install()
        self.execute.assert_called_once_with(
            previous/'Pointer.exe', ['--apply', '--install-dir', str(previous), '--data-dir', str(previous.parent/'data')],
            previous.parent/'data'/'rollback-resume-report.json', upgrade_resume=True)
        self.assertFalse(self.running)
        self.assertFalse(path.exists())
        self.assertEqual((self.target/'Pointer.exe').read_bytes(), b'old')
        self.startup_enable.assert_not_called()
        self.assert_originals()

    def test_previous_handoff_restores_previous_directory_after_new_resume_failure(self):
        previous, path, _ = self.write_previous_handoff()
        def resume(executable, arguments, report, *, upgrade_resume=False):
            if executable.parent == self.target:
                raise RuntimeError('new helper failed')
            self.assertEqual(executable, previous/'Pointer.exe')
            self.assertEqual(arguments, ['--apply', '--install-dir', str(previous), '--data-dir', str(previous.parent/'data')])
            self.assertEqual(report.parent, previous.parent/'data')
            return {'running': True}
        self.execute.side_effect = resume
        with self.assertRaisesRegex(RuntimeError, 'new helper failed'):
            installation.install()
        self.assertEqual([call.args[0] for call in self.execute.call_args_list],
                         [self.target/'Pointer.exe', previous/'Pointer.exe'])
        self.assertFalse(self.running)
        self.assertFalse(path.exists())
        self.assertEqual((self.target/'Pointer.exe').read_bytes(), b'old')
        self.assertEqual((previous/'Pointer.exe').read_bytes(), b'previous')
        self.startup_enable.assert_called_once_with()
        self.assert_originals()

    def test_previous_handoff_recovers_prepared_service_when_backup_fails_before_stop(self):
        previous, path, _ = self.write_previous_handoff()
        self.migrate.side_effect = OSError('backup failed')
        self.execute.side_effect = None
        self.execute.return_value = {'running': True}
        with self.assertRaisesRegex(OSError, 'backup failed'):
            installation.install()
        self.stop.assert_not_called()
        self.execute.assert_called_once_with(
            previous/'Pointer.exe', ['--apply', '--install-dir', str(previous), '--data-dir', str(previous.parent/'data')],
            previous.parent/'data'/'rollback-resume-report.json', upgrade_resume=True)
        self.assertFalse(self.running)
        self.assertFalse(path.exists())
        self.startup_enable.assert_not_called()
        self.assert_originals()

    def test_real_cli_apply_double_failure_retains_previous_intent_for_retry(self):
        previous, path, _ = self.write_previous_handoff()
        intent = path.read_bytes()
        settings_before = (self.data/'settings.json').read_bytes()
        self.backend.stop.side_effect = self.stop_runtime
        failure = True
        def start():
            self.assertEqual(path.read_bytes(), intent)
            self.assertNotIn('POINTER_UPGRADE_HANDOFF', os.environ)
            if failure:
                raise RuntimeError('new helper failed')
            self.running = True
            return {'running': True}
        self.backend.start.side_effect = start
        self.backend.restore.side_effect = RuntimeError('registry restore failed')
        with patch.object(installation, '_execute', self.real_execute), \
                patch.object(installation.subprocess, 'run', side_effect=self.bridge_real_cli) as child:
            with self.assertRaisesRegex(RuntimeError, 'new helper failed.*registry restore failed'):
                installation.install()
            self.assertEqual(self.backend.restore.call_count, 2)
            self.assertEqual(child.call_count, 1)
            self.assertFalse(self.running)
            self.assertEqual(path.read_bytes(), intent)
            self.assertEqual((self.data/'settings.json').read_bytes(), settings_before)
            self.assertEqual((self.target/'Pointer.exe').read_bytes(), b'old')
            self.assertEqual((previous/'Pointer.exe').read_bytes(), b'previous')
            self.assert_originals()
            failure = False
            self.backend.restore.side_effect = None
            self.assertTrue(installation.install()['installed'])
        self.assertEqual(child.call_count, 2)
        self.assertEqual([event for event in self.events if event.startswith('cli:')], ['cli:new', 'cli:new'])
        self.assertTrue(self.running)
        self.assertFalse(path.exists())
        self.assertEqual((self.target/'Pointer.exe').read_bytes(), b'new')
        self.assert_originals()

    def test_real_cli_apply_keeps_handoff_until_old_directory_recovery_completes(self):
        previous, path, _ = self.write_previous_handoff()
        intent = path.read_bytes()
        self.backend.stop.side_effect = self.stop_runtime
        def start():
            self.assertEqual(path.read_bytes(), intent)
            if self.backend.start.call_count == 1:
                raise RuntimeError('new helper failed')
            self.running = True
            return {'running': True}
        self.backend.start.side_effect = start
        with patch.object(installation, '_execute', self.real_execute), \
                patch.object(installation.subprocess, 'run', side_effect=self.bridge_real_cli) as child:
            with self.assertRaisesRegex(RuntimeError, 'new helper failed'):
                installation.install()
        self.assertEqual([Path(call.args[0][0]) for call in child.call_args_list],
                         [self.target/'Pointer.exe', previous/'Pointer.exe'])
        self.assertEqual([event for event in self.events if event.startswith('cli:')], ['cli:new', 'cli:previous'])
        self.assertTrue(self.running)
        self.assertFalse(path.exists())
        self.assertEqual((self.target/'Pointer.exe').read_bytes(), b'old')
        self.assertEqual((previous/'Pointer.exe').read_bytes(), b'previous')
        self.assert_originals()

    def test_previous_handoff_requires_matching_verified_directory_and_managed_cursor(self):
        previous, path, payload = self.write_previous_handoff()
        for label in ('directory', 'cursor', 'unverified', 'invalid_running'):
            with self.subTest(label=label):
                saved = json.loads(json.dumps(payload))
                current = json.loads(json.dumps(self.before))
                if label == 'directory':
                    saved['previous_root'] = str(self.root/'foreign'/'app')
                elif label == 'cursor':
                    saved['registry']['cursor_values']['Arrow']['value'] = str(self.root/'foreign'/'arrow.cur')
                    current['registry'] = saved['registry']
                elif label == 'invalid_running':
                    saved['running'] = 'false'
                path.write_text(json.dumps(saved), encoding='utf-8')
                matched = None if label == 'unverified' else previous
                self.assertIsNone(installation._upgrade_handoff(self.data, self.target, current, matched))
        self.execute.assert_not_called()
        self.startup_enable.assert_not_called()
        self.assert_originals()

    def test_damaged_previous_package_is_never_resumed_from_handoff(self):
        previous, path, _ = self.write_previous_handoff()
        (previous/'Pointer.exe').write_bytes(b'corrupt')
        original = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'checksum'):
            installation.install()
        self.stop.assert_not_called()
        self.execute.assert_not_called()
        self.startup_enable.assert_not_called()
        self.assertEqual(path.read_bytes(), original)
        self.assert_originals()

    def test_running_success_consumes_old_handoff_before_later_paused_upgrade(self):
        path, _ = self.write_legacy_handoff()
        self.running = True
        installation.install()
        self.assertTrue(self.running)
        self.assertFalse(path.exists())
        self.assertEqual(self.events[-1], 'resume:new')
        self.running = False
        self.events.clear()
        self.execute.reset_mock()
        installation.install()
        self.execute.assert_not_called()
        self.assertFalse(self.running)
        self.assertEqual(self.events, ['gate', 'snapshot', 'stop'])
        self.assert_originals()

    def test_unrelated_handoff_remains_after_running_install(self):
        path, payload = self.write_legacy_handoff()
        payload['upgrade_install_root'] = str(self.root/'other-app')
        path.write_text(json.dumps(payload), encoding='utf-8')
        original = path.read_bytes()
        self.running = True
        installation.install()
        self.assertTrue(self.running)
        self.assertEqual(path.read_bytes(), original)
        self.assert_originals()

    def test_legacy_handoff_consumed_after_failure_recovery(self):
        path, _ = self.write_legacy_handoff()
        with patch.object(installation, 'deploy_package', side_effect=RuntimeError('deploy failed')):
            with self.assertRaisesRegex(RuntimeError, 'deploy failed'):
                installation.install()
        self.assertEqual(self.events[-1], 'resume:old')
        self.assertFalse(path.exists())
        self.assertTrue(self.running)

    def test_legacy_handoff_retained_when_recovery_fails(self):
        path, _ = self.write_legacy_handoff()
        original = path.read_bytes()
        self.backend.restore.side_effect = RuntimeError('restore failed')
        with patch.object(installation, 'deploy_package', side_effect=RuntimeError('deploy failed')):
            with self.assertRaisesRegex(RuntimeError, 'deploy failed.*restore failed'):
                installation.install()
        self.assertEqual(path.read_bytes(), original)

    def test_newer_handoff_is_not_deleted(self):
        path, _ = self.write_legacy_handoff()
        def resume_and_replace(executable, arguments, report, *, upgrade_resume=False):
            path.write_bytes(b'new transaction')
            return self.resume_runtime(executable, arguments, report)
        self.execute.side_effect = resume_and_replace
        installation.install()
        self.assertEqual(path.read_bytes(), b'new transaction')

    def test_stale_malformed_paused_or_foreign_handoff_ignored(self):
        path, payload = self.write_legacy_handoff()
        before = {**self.before, 'running': False}
        for label in ('malformed', 'missing', 'paused', 'settings', 'old', 'future', 'foreign', 'identity'):
            with self.subTest(label=label):
                saved = json.loads(json.dumps(payload))
                current = json.loads(json.dumps(before))
                if label == 'missing':
                    saved.pop('registry')
                elif label == 'paused':
                    saved['running'] = False
                elif label == 'settings':
                    saved['settings']['motion'] = 'shrink'
                elif label == 'foreign':
                    saved['registry']['cursor_values']['Arrow']['value'] = str(self.root/'foreign/data/cursor.cur')
                    current['registry'] = saved['registry']
                elif label == 'identity':
                    saved['upgrade_install_root'] = str(self.root/'other-app')
                path.write_text('not json' if label == 'malformed' else json.dumps(saved), encoding='utf-8')
                if label in ('old', 'future'):
                    stamp = installation.time.time() + (-901 if label == 'old' else 60)
                    os.utime(path, (stamp, stamp))
                original = path.read_bytes()
                self.assertIsNone(installation._upgrade_handoff(self.data, self.target, current))
                self.assertEqual(path.read_bytes(), original)


class UpgradeIPCTests(unittest.TestCase):
    def setUp(self):
        from pointer.windows import gui_ipc
        self.ipc = gui_ipc
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        self.request, self.reply = root/'request.json', root/'reply.json'
        self.kernel = Mock()
        self.kernel.OpenMutexW.return_value = 1
        self.kernel.WaitForSingleObject.return_value = gui_ipc.WAIT_TIMEOUT
        for name, value in (('REQUEST', self.request), ('REPLY', self.reply), ('INSTALL_ROOT', root/'app'), ('KERNEL32', self.kernel)):
            self.stack.enter_context(patch.object(gui_ipc, name, value))
        self.stack.enter_context(patch.object(gui_ipc.uuid, 'uuid4', return_value=Mock(hex='request-token')))

    def test_no_gui_requires_no_request_or_native_mutation(self):
        self.kernel.OpenMutexW.return_value = 0
        self.ipc.prepare_gui_upgrade()
        self.assertFalse(self.request.exists())
        self.kernel.WaitForSingleObject.assert_not_called()
        self.kernel.ReleaseMutex.assert_not_called()

    def test_detached_gui_reply_allows_installer_and_cleans_request(self):
        self.reply.write_text(json.dumps({'token': 'request-token', 'ready': True, 'detached': True}))
        self.ipc.prepare_gui_upgrade()
        self.assertFalse(self.request.exists())
        self.kernel.CloseHandle.assert_called_once_with(1)
        self.kernel.ReleaseMutex.assert_not_called()

    def test_rejected_gui_reply_aborts_and_closes_handle(self):
        self.reply.write_text(json.dumps({'token': 'request-token', 'ready': False, 'error': 'dirty draft'}))
        with self.assertRaisesRegex(RuntimeError, 'dirty draft'):
            self.ipc.prepare_gui_upgrade()
        self.assertFalse(self.request.exists())
        self.kernel.CloseHandle.assert_called_once_with(1)

    def test_unresponsive_gui_times_out_and_closes_handle(self):
        with patch.object(self.ipc.time, 'monotonic', side_effect=[0, 0, 9]):
            with self.assertRaisesRegex(RuntimeError, '设置窗口未退出'):
                self.ipc.prepare_gui_upgrade()
        self.assertFalse(self.request.exists())
        self.kernel.CloseHandle.assert_called_once_with(1)
