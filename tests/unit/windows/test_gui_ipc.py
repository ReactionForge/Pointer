import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from pointer.windows import gui_ipc


class GuiIPCTests(unittest.TestCase):
    def test_expired_upgrade_request_is_not_replayed_on_next_launch(self):
        self.assertTrue(hasattr(gui_ipc,'read_request'),'Upgrade request expiry missing')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'request.json'
            path.write_text(json.dumps({'token':'old','created':time.time()-60}))
            with patch.object(gui_ipc,'REQUEST',path):
                self.assertIsNone(gui_ipc.read_request())
                path.write_text(json.dumps({'token':'new','created':time.time()}))
                self.assertEqual(gui_ipc.read_request()['token'],'new')
