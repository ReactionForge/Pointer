"""Resolve command path overrides before Windows modules capture their paths."""
import os
import sys


def configure_paths(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    for flag, name in (('--data-dir', 'POINTER_DATA_DIR'), ('--install-dir', 'POINTER_INSTALL_DIR')):
        for index, arg in enumerate(args):
            if arg == flag and index + 1 < len(args):
                os.environ[name] = os.path.abspath(args[index + 1])
            elif arg.startswith(flag + '='):
                os.environ[name] = os.path.abspath(arg.split('=', 1)[1])
