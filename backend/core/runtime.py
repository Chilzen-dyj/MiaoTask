"""Asset and writable-data paths for source and frozen distributions."""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]


def assets_dir():
    return Path(getattr(sys, '_MEIPASS', ROOT))


def data_dir():
    override = os.environ.get('MIAO_DATA_DIR')
    if override:
        path = Path(override).expanduser().resolve()
    elif getattr(sys, 'frozen', False):
        path = Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'MiaoTask'
    else:
        path = ROOT / 'runtime'
    path.mkdir(parents=True, exist_ok=True)
    return path


def version():
    return json.loads((assets_dir() / 'version.json').read_text(encoding='utf-8'))['version']
