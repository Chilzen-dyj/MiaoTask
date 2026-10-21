# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os
import shutil

from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs, collect_submodules, copy_metadata

root = Path(SPECPATH)
datas = [(str(root / 'version.json'), '.'), (str(root / 'configs'), 'configs'), (str(root / 'web'), 'web')]
binaries = collect_dynamic_libs('onnxruntime')
for package in ('uiautomator2', 'hmdriver2', 'rapidocr'):
    datas += collect_data_files(package)
for package in ('uiautomator2', 'hmdriver2', 'rapidocr', 'onnxruntime', 'numpy', 'Pillow'):
    datas += copy_metadata(package, recursive=True)

for tool in ('adb', 'hdc'):
    supplied = os.environ.get(f'MIAO_{tool.upper()}_DIR')
    executable = str(Path(supplied) / f'{tool}.exe') if supplied else shutil.which(tool)
    if executable and Path(executable).is_file():
        folder = Path(executable).parent
        binaries.append((executable, 'tools'))
        binaries.extend((str(dll), 'tools') for dll in folder.glob('*.dll'))
    elif tool == 'adb':
        raise RuntimeError('ADB is required for this release build')

a = Analysis([str(root / 'main.py')], pathex=[str(root)], binaries=binaries, datas=datas,
             hiddenimports=collect_submodules('modules') + collect_submodules('rapidocr'),
             hookspath=[], hooksconfig={}, runtime_hooks=[],
             excludes=['torch', 'tensorflow', 'paddle', 'matplotlib', 'pytest', 'IPython'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='MiaoTask',
          icon=str(root / 'web/assets/miaotask.ico'),
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
          console=False, disable_windowed_traceback=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='MiaoTask')
