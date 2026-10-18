"""Offline, device-free checks run inside the packaged executable."""
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from modules.runtime import assets_dir, version


def self_test(output):
    checks, errors = {}, []
    for name in ('uiautomator2', 'hmdriver2', 'rapidocr', 'onnxruntime', 'numpy', 'Pillow'):
        try:
            checks[name] = importlib.metadata.version(name)
        except Exception as exc:
            errors.append(f'{name}: {exc}')
    for name in ('web/index.html', 'web/app.js', 'web/style.css', 'configs/double11.json'):
        checks[name] = (assets_dir() / name).is_file()
        if not checks[name]:
            errors.append(f'Missing asset: {name}')
    try:
        adb = shutil.which('adb')
        if not adb:
            raise RuntimeError('ADB not found')
        result = subprocess.run([adb, 'version'], capture_output=True, text=True, timeout=10,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        checks['adb_bundled'] = Path(adb).is_relative_to(assets_dir()) if getattr(sys, 'frozen', False) else True
        checks['adb_version'] = result.stdout.splitlines()[0]
        if result.returncode or not checks['adb_bundled']:
            errors.append('Bundled ADB validation failed')
    except Exception as exc:
        errors.append(f'ADB: {exc}')
    try:
        from PIL import Image, ImageDraw, ImageFont
        from modules.screen_reader import ScreenReader
        image = Image.new('RGB', (900, 180), 'white')
        ImageDraw.Draw(image).text((30, 45), 'BROWSE 15 SECONDS', fill='black', font=ImageFont.load_default(size=52))
        recognized = ScreenReader(None)._ocr(image)
        text = ' '.join(n.text for n in recognized)
        checks['ocr_text'] = text
        if '15' not in text:
            errors.append('OCR did not recognize the offline test image')
    except Exception as exc:
        errors.append(f'OCR: {type(exc).__name__}: {exc}')
    report = dict(ok=not errors, version=version(), frozen=bool(getattr(sys, 'frozen', False)),
                  platform=platform.platform(), python=platform.python_version(), checks=checks, errors=errors)
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report
