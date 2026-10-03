"""Run the same command interface as the packaged Windows executable."""

from pointer.bootstrap import configure_paths
configure_paths()
from pointer.cli import main

raise SystemExit(main())
