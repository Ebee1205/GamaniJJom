"""Separate bundled resources from persistent files in a frozen Windows build."""
import json
import os
from pathlib import Path
import sys


def is_frozen() -> bool:
    return bool(getattr(sys, 'frozen', False))


def bundle_root() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent.parent


def data_root() -> Path:
    if is_frozen():
        local = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local'))
        return local / 'GamaniJJom'
    return bundle_root()


def default_config_path() -> Path:
    if is_frozen():
        return data_root() / 'gamani-jjom.cfg.json'
    return bundle_root() / 'src' / 'config' / 'gamani-jjom.cfg.json'


def prepare_default_config() -> None:
    """Seed writable settings once; never replace saved user preferences."""
    target = default_config_path()
    if not is_frozen() or target.exists():
        return
    template = bundle_root() / 'src' / 'config' / 'gamani-jjom.prod.cfg.json'
    settings = json.loads(template.read_text(encoding='utf-8-sig'))
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also protects preferences when two instances start.
    try:
        with target.open('x', encoding='utf-8') as output:
            json.dump(settings, output, ensure_ascii=False, indent=2)
            output.write('\n')
    except FileExistsError:
        pass
