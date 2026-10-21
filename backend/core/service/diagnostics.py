"""Offline, device-free checks run inside the packaged executable."""
import importlib.metadata
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys

from backend.core.runtime import assets_dir, version


def self_test(output):
    checks, errors = {}, []
    for name in ('uiautomator2', 'hmdriver2', 'rapidocr', 'onnxruntime', 'numpy', 'Pillow'):
        try:
            checks[name] = importlib.metadata.version(name)
        except Exception as exc:
            errors.append(f'{name}: {exc}')
    for name in ('frontend/index.html', 'frontend/js/app.js', 'frontend/css/base.css', 'backend/core/config/defaults.json'):
        checks[name] = (assets_dir() / name).is_file()
        if not checks[name]:
            errors.append(f'Missing asset: {name}')
    try:
        from types import SimpleNamespace
        from backend.core.registry import default_registry
        from backend.core.config.loader import load_resolved
        registry = default_registry()
        count = 0
        for app in registry.catalog():
            for activity in app['activities']:
                registration = registry.get(app['id'], activity['id'])
                config = load_resolved(registration).mutable()
                # Constructor only: this stub has no device I/O methods.
                device = SimpleNamespace(device_type=registration.activity.device_types[0], selected_instance=None)
                runner = registry.instantiate(device, config, app=app['id'], activity=activity['id'])
                if runner.config != config:
                    raise ValueError('Activity configuration mismatch')
                count += 1
        checks['registered_activities'] = count
        checks['activity_factories'] = True
    except Exception as exc:
        errors.append(f'Registry: {type(exc).__name__}: {exc}')
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
        from backend.core.device.screen import ScreenReader
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
