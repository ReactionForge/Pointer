"""Keep source launchers and the frozen Windows build on one application entry."""

from pathlib import Path
import sys

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from pointer.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
