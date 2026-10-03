"""Native loading uses the configured canvas; profiles cannot escape owned roots."""
import ctypes
from ctypes import wintypes
import inspect
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch
from pointer.cursor.settings import CursorSettings
from pointer.cursor.theme import theme_paths, click_paths
from pointer.windows import engine


class EngineProfileTests(unittest.TestCase):
    def run_stopped_loop(self):
        from pointer.cursor import motion
        from pointer.cursor.theme import THEME_NAME
        normal=Mock(notes=[]);clicked=Mock(notes=[]);kernel=Mock()
        kernel.WaitForSingleObject.side_effect=[258,258,0]
        profile={'settings':{'appearance':'light','motion':'tilt'},'themes':{},'frames':{},'size':64}
        with ExitStack() as stack:
            stack.enter_context(patch.object(engine,'KERNEL32',kernel))
            user=stack.enter_context(patch.object(engine,'USER32'));user.GetAsyncKeyState.return_value=0
            stack.enter_context(patch.object(engine,'_scheme_name',return_value=THEME_NAME))
            stack.enter_context(patch.object(engine,'_set_dpi_awareness'))
            stack.enter_context(patch.object(engine,'_cursor_dpi',return_value=144))
            stack.enter_context(patch.object(engine,'_read_profile',return_value=profile))
            stack.enter_context(patch.object(engine,'_initial_theme',return_value='light'))
            stack.enter_context(patch.object(engine,'_atomic_json'))
            cache=stack.enter_context(patch.object(engine,'_CursorCache',side_effect=[normal,clicked]))
            moving=stack.enter_context(patch.object(motion,'ClickMotion')).return_value
            moving.update.return_value=4;moving.presses=1
            ctypes.set_last_error(0)
            engine._run()
        self.assertEqual(cache.call_args_list[0].kwargs['size'],96)
        return normal,clicked

    def test_initial_theme_applies_all_roles_at_physical_size(self):
        from pointer.cursor.theme import ROLE_IDS, THEME_NAME
        normal,_=self.run_stopped_loop()
        normal.apply.assert_any_call('light',ROLE_IDS,THEME_NAME)

    def test_graceful_stop_resets_pressed_roles(self):
        _,clicked=self.run_stopped_loop()
        self.assertEqual(clicked.apply.call_args.args[0],'light:0')

    def test_ready_token_accepts_windows_launcher_child_pid(self):
        process = Mock(pid=100)
        process.poll.return_value = None
        environment = {}
        def launch(*args, **kwargs):
            environment.update(kwargs['env'])
            return process
        def status():
            return {'pid':101,'running':True,'launch_token':environment.get('POINTER_LAUNCH_TOKEN')}
        with patch.object(engine,'_running',side_effect=[False,True]), \
             patch.object(engine.subprocess,'Popen',side_effect=launch), \
             patch.object(engine,'_read_status',side_effect=status):
            self.assertTrue(engine.start()['running'])

    def test_cache_loads_requested_physical_canvas(self):
        self.assertIn('size', inspect.signature(engine._CursorCache).parameters)
        cache = engine._CursorCache({'light': {'Arrow': theme_paths('light')['Arrow']}}, size=48)
        class Info(ctypes.Structure):
            _fields_ = [('icon', wintypes.BOOL), ('x', wintypes.DWORD), ('y', wintypes.DWORD),
                        ('mask', wintypes.HBITMAP), ('color', wintypes.HBITMAP)]
        class Bitmap(ctypes.Structure):
            _fields_ = [('type', wintypes.LONG), ('width', wintypes.LONG), ('height', wintypes.LONG),
                        ('stride', wintypes.LONG), ('planes', wintypes.WORD), ('bitsperpixel', wintypes.WORD),
                        ('bits', ctypes.c_void_p)]
        engine.USER32.GetIconInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Info)]
        engine.USER32.GetIconInfo.restype = wintypes.BOOL
        engine.GDI32.GetObjectW.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p]
        engine.GDI32.GetObjectW.restype = ctypes.c_int
        info = Info()
        try:
            self.assertTrue(engine.USER32.GetIconInfo(cache.handles['light', 'Arrow'], ctypes.byref(info)))
            bitmap = Bitmap()
            self.assertTrue(engine.GDI32.GetObjectW(info.color, ctypes.sizeof(bitmap), ctypes.byref(bitmap)))
            self.assertEqual((bitmap.width, bitmap.height), (48, 48))
        finally:
            for handle in (info.mask, info.color):
                if handle:
                    engine.GDI32.DeleteObject(handle)
            cache.close()

    def test_profile_rejects_external_resource_path_before_loading(self):
        self.assertTrue(hasattr(engine, '_read_profile'), 'Profile API missing')
        value = {'key': 'builtin', 'size': 32, 'settings': CursorSettings().to_dict(),
                 'themes': {t: {r:str(p) for r,p in theme_paths(t).items()} for t in ('light','dark')},
                 'frames': {f'{t}:{f}': {r:str(p) for r,p in click_paths(t,f,'tilt').items()}
                            for t in ('light','dark') for f in range(5)}}
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'profile.json'
            path.write_text(json.dumps(value))
            self.assertEqual(engine._read_profile(path)['size'], 32)
            value['themes']['light']['Arrow'] = str(Path(folder) / 'outside.cur')
            path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):
                engine._read_profile(path)
