import unittest
from unittest.mock import patch
from scripts import build_release


class BuildTests(unittest.TestCase):
    def test_build_path_excludes_unrelated_icu_libraries(self):
        self.assertTrue(hasattr(build_release,'clean_build_environment'),'Isolated build environment missing')
        with patch.dict(build_release.os.environ,{'PATH':r'C:\foreign\poppler\bin;C:\Windows\System32'}):
            value=build_release.clean_build_environment()
            self.assertNotIn('poppler',value['PATH'])
            self.assertIn('System32',value['PATH'])

    def test_preview_version_keeps_numeric_windows_version(self):
        self.assertTrue(hasattr(build_release,'parse_version'),'Preview version parser missing')
        self.assertEqual(build_release.parse_version('1.3.0-beta.1'),((1,3,0,0),'1.3.0-beta.1'))
        for value in ('1.3.0/../bad','1.3.0-beta.1;cmd','01.3.0','1.3.0-beta.0'):
            with self.assertRaises(ValueError):
                build_release.parse_version(value)
