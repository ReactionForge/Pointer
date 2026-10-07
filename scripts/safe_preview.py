"""Process-local update isolation for Pointer's Mock review entry points only."""
from contextlib import contextmanager, ExitStack
from unittest.mock import patch
from pointer.ui.main_window import MainWindow

ISOLATED_UPDATE_MESSAGE = '隔离预览：不检查、下载或安装更新。'


class SafePreviewWindow(MainWindow):
    def __init__(self, backend):
        super().__init__(backend)
        self.pages[3].update_status_lbl.setText(ISOLATED_UPDATE_MESSAGE)

    def _blocked_update(self, *args, **kwargs):
        self.pages[3].update_status_lbl.setText(ISOLATED_UPDATE_MESSAGE)
        self.feedback.setText(ISOLATED_UPDATE_MESSAGE)
        self.toast.show_message(ISOLATED_UPDATE_MESSAGE)

    # Override before PreferencesPage connects its button, including callbacks
    # that could otherwise create a real update dialog or worker.
    check_updates_interactive = _blocked_update
    _check_update_silent_startup = _blocked_update
    _show_update_dialog = _blocked_update


@contextmanager
def isolated_update_services():
    """Defense in depth; never replace updater behavior in the shipped app."""
    def blocked(*args, **kwargs):
        raise RuntimeError(ISOLATED_UPDATE_MESSAGE)
    with ExitStack() as stack:
        for target in ('pointer.updater.check_for_updates',
                       'pointer.updater.download_update_package',
                       'pointer.updater.trigger_silent_upgrade',
                       'pointer.ui.update_dialog.download_update_package',
                       'pointer.ui.update_dialog.trigger_silent_upgrade'):
            stack.enter_context(patch(target, side_effect=blocked))
        yield
