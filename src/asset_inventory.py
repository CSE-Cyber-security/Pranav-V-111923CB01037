"""Start the asset management menu."""

from pathlib import Path
import sys


# Allow this script to run directly from the src folder.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["--menu", *sys.argv[1:]]))
