import unittest, importlib.util
from pathlib import Path

class ArchitectureTests(unittest.TestCase):
 def test_installed_sibling_data_survives_host_virtualization(self):
  self.assertIsNotNone(importlib.util.find_spec("pointer.paths"), "New paths module missing")
  from pointer.paths import resolve_paths
  root = Path("C:/Users/test/AppData/Local/Packages/Host/LocalCache/Local/Pointer/app")
  paths = resolve_paths(root, Path("C:/Users/test/AppData/Local"), True)
  self.assertEqual(paths.data_root, root.parent / "data")
