import os
import sys
from pathlib import Path
from unittest.mock import Mock

os.environ['QT_QPA_PLATFORM'] = 'offscreen'

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / 'src'))

from PySide6.QtWidgets import QApplication
from pointer.ui.main_window import MainWindow
from pointer.cursor.settings import CursorSettings

def main():
    app = QApplication.instance() or QApplication(sys.argv)
    
    settings = CursorSettings()
    mock_app = Mock()
    mock_app.settings.return_value = settings
    mock_app.backend.snapshot.return_value = {'running': True, 'startup_enabled': True}
    
    window = MainWindow(mock_app)
    window.resize(1120, 750)
    window.show()
    app.processEvents()

    out_dir = repo_root / 'docs' / 'images'
    out_dir.mkdir(parents=True, exist_ok=True)

    pages = [
        (0, 'app_preview_appearance.png'),
        (1, 'app_preview_motion.png'),
        (2, 'app_preview_tests.png'),
        (3, 'app_preview_preferences.png'),
    ]

    for idx, filename in pages:
        window.select_page(idx)
        app.processEvents()
        
        pixmap = window.grab()
        target = out_dir / filename
        pixmap.save(str(target), 'PNG')
        print(f"Saved: {target} ({pixmap.width()}x{pixmap.height()})")

    window.discard_changes()
    window.close()
    print("All captures completed successfully.")

if __name__ == '__main__':
    main()
