"""Release icons and shortcuts use the accepted artwork at every entry point."""
import base64
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from scripts import build_release
from pointer.windows import installation

ROOT = Path(__file__).resolve().parents[3]


class ReleaseIconTests(unittest.TestCase):
    def test_accepted_icon_contains_shell_and_high_dpi_sizes(self):
        with Image.open(ROOT / 'packaging/windows/pointer.ico') as icon:
            self.assertEqual(icon.ico.sizes(), {(n,n) for n in (16,24,32,48,64,128,256)})
            for size in icon.ico.sizes():
                self.assertTrue(icon.ico.getimage(size).getbbox(), size)

    def test_installer_shortcuts_and_uninstall_bind_the_packaged_icon(self):
        text = (ROOT / 'packaging/windows/installer.iss').read_text(encoding='utf-8')
        self.assertIn('UninstallDisplayIcon={app}\\pointer.ico', text)
        shortcuts = [line for line in text.splitlines() if line.startswith('Name: "{group}\\')
                     or line.startswith('Name: "{autodesktop}\\')]
        self.assertEqual(len(shortcuts), 3)
        for shortcut in shortcuts:
            self.assertIn('IconFilename: "{app}\\pointer.ico"', shortcut)
            self.assertIn('IconIndex: 0', shortcut)

    def test_zip_shortcuts_bind_icon_without_using_user_startup(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            with patch.dict(os.environ, {'APPDATA':str(root/'roaming')}), \
                 patch.object(installation, 'INSTALL_ROOT', root/'app'), \
                 patch.object(installation.subprocess, 'run') as run:
                installation._shortcuts()
            command = run.call_args.args[0]
            script = base64.b64decode(command[-1]).decode('utf-16-le')
            self.assertEqual(script.count('$pointerShortcut.IconLocation = '), 2)
            self.assertIn(str((root/'app/pointer.ico').resolve()) + ',0', script)
            self.assertNotIn('CurrentVersion\\Run', script)

    def test_installer_refreshes_own_icons_after_post_install_deployment(self):
        text = (ROOT / 'packaging/windows/installer.iss').read_text(encoding='utf-8')
        shortcuts = text.split('[Icons]', 1)[1].split('[Run]', 1)[0]
        for line in shortcuts.splitlines():
            if line.startswith('Name:'):
                self.assertNotIn('BeforeInstall:', line, 'Do not commit outside the post-install transaction boundary')
        self.assertIn('procedure EnsurePayloadDeployed;', text)
        self.assertIn('if PayloadDeployed then', text)
        self.assertIn('PayloadDeployed := True;', text)
        callback = text.split('procedure CurStepChanged', 1)[1].split('function InitializeUninstall', 1)[0]
        self.assertIn('if CurStep = ssPostInstall then', callback)
        self.assertLess(callback.index('EnsurePayloadDeployed;'), callback.index('RefreshPointerIcons;'))
        self.assertIn('NotifyChangedIcon($2000, $2005,', text)
        self.assertNotIn('SHCNE_ASSOCCHANGED', text)

    def test_build_rejects_unrelated_embedded_artwork(self):
        self.assertTrue(hasattr(build_release, 'verify_executable_icon'), 'Release icon verification missing')
        with self.assertRaisesRegex(ValueError, 'accepted artwork'):
            build_release.verify_executable_icon(Path(sys.executable), ROOT/'packaging/windows/pointer.ico')
