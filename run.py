from __future__ import annotations

from pathlib import Path
import os

from server import main


if __name__ == "__main__":
    os.chdir(Path(__file__).resolve().parent)
    main(open_browser=True)
