"""Keep print/logging compatible with the console-free PyInstaller bootloader."""
import os
from pathlib import Path
import sys

if sys.stdout is None or sys.stderr is None:
    directory = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'GamaniJJom'
    directory.mkdir(parents=True, exist_ok=True)
    stream = (directory / 'startup.log').open('a', encoding='utf-8', buffering=1)
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream
