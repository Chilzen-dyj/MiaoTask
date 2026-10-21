"""Build a tested, self-contained Windows zip using an explicit file allowlist."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parent.parent
PORTABLE_DOCS = ('USAGE.md', 'SAFETY.md', 'ATTRIBUTION.md', 'RELEASES.md')


def copy_documentation(destination):
    """Keep portable help in the same relative layout as the source docs."""
    folder = destination / 'docs'
    folder.mkdir(parents=True, exist_ok=True)
    for name in PORTABLE_DOCS:
        shutil.copy2(ROOT / 'docs' / name, folder / name)
    (destination / 'README.md').write_text(
        '# MiaoTask\n\n'
        '双击 `MiaoTask.exe`，保留 `_internal/`。升级前先退出旧助手。\n\n'
        '[使用说明](docs/USAGE.md) · [风险与隐私](docs/SAFETY.md) · '
        '[发布记录](docs/RELEASES.md) · [来源说明](docs/ATTRIBUTION.md)\n',
        encoding='utf-8')


def source_commit():
    """Record the public source revision and refuse an uncommitted release build."""
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    status = subprocess.check_output(['git', 'status', '--porcelain', '--untracked-files=normal'],
                                     cwd=ROOT, text=True)
    if status.strip():
        raise RuntimeError('Commit the clean source tree before building a release')
    subprocess.run([sys.executable, 'scripts/check_public_files.py'], cwd=ROOT, check=True)
    return commit


def licenses(destination, adb_dir):
    destination.mkdir(parents=True, exist_ok=True)
    for dist in metadata.distributions():
        name = dist.metadata['Name']
        for relative in dist.files or []:
            path = str(relative)
            if '.dist-info/' not in path or not re.search(r'license|copying|notice', path, re.I):
                continue
            source = Path(dist.locate_file(relative))
            if source.is_file():
                target = destination / name / Path(path.split('.dist-info/', 1)[1])
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
    python_license = Path(sys.base_prefix) / 'LICENSE.txt'
    if python_license.is_file():
        shutil.copy2(python_license, destination / 'Python-LICENSE.txt')
    adb_notice = adb_dir / 'NOTICE.txt'
    if not adb_notice.is_file():
        raise RuntimeError('ADB NOTICE.txt is required for the portable distribution')
    shutil.copy2(adb_notice, destination / 'Android-platform-tools-NOTICE.txt')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--adb-dir', help='Folder containing adb.exe, DLLs and NOTICE.txt')
    parser.add_argument('--hdc-dir', help='Optional authorized HDC runtime folder')
    parser.add_argument('--skip-tests', action='store_true', help='Skip unit tests already run on this commit')
    args = parser.parse_args()
    if sys.platform != 'win32' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise SystemExit('Build this package on Windows x64')
    revision = source_commit()
    adb = shutil.which('adb')
    adb_dir = Path(args.adb_dir).resolve() if args.adb_dir else Path(adb).parent if adb else ROOT / 'build/vendor/platform-tools'
    if not all((adb_dir / name).is_file() for name in ('adb.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll', 'NOTICE.txt')):
        raise SystemExit('ADB missing: run python scripts/fetch_platform_tools.py or pass --adb-dir')
    if not args.skip_tests:
        subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-q'], cwd=ROOT, check=True)
    version = json.loads((ROOT / 'version.json').read_text(encoding='utf-8'))['version']
    if not re.fullmatch(r'[A-Za-z0-9._-]+', version):
        raise SystemExit('Invalid release version')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S-%f')
    dist = (ROOT / 'dist' / f'windows-{stamp}').resolve()
    work = (ROOT / 'build' / f'pyinstaller-{stamp}').resolve()
    if not dist.is_relative_to(ROOT / 'dist') or not work.is_relative_to(ROOT / 'build'):
        raise SystemExit('Build path escapes the workspace')
    env = os.environ.copy()
    env['MIAO_ADB_DIR'] = str(adb_dir)
    if args.hdc_dir:
        env['MIAO_HDC_DIR'] = str(Path(args.hdc_dir).resolve())
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--distpath', str(dist),
                    '--workpath', str(work), str(ROOT / 'build.spec')], env=env, cwd=ROOT, check=True)
    package = dist / 'MiaoTask'
    executable = package / 'MiaoTask.exe'
    copy_documentation(package)
    licenses(package / 'licenses', adb_dir)
    from smoke_packaged import smoke
    smoke(executable, package / 'self-test.json')
    manifest = dict(version=version, platform='windows-x64', python=platform.python_version(),
                    source_commit=revision, source_repository='https://github.com/h0ll0w-AkuZr0guY/tmall-miao-double11',
                    built_utc=datetime.now(timezone.utc).isoformat(),
                    packages={d.metadata['Name']: d.version for d in metadata.distributions()},
                    adb_bundled=True, hdc_bundled=(package / '_internal/tools/hdc.exe').exists(),
                    offline_models=True, smoke_test_passed=True)
    (package / 'build-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    archive = ROOT / 'dist' / f'MiaoTask-{version}-windows-x64.zip'
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(package.rglob('*')):
            if path.is_file():
                if path.is_symlink() or not path.resolve().is_relative_to(package.resolve()):
                    raise RuntimeError(f'Unsafe package member: {path.name}')
                bundle.write(path, Path('MiaoTask') / path.relative_to(package))
    with archive.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    archive.with_suffix(archive.suffix + '.sha256').write_text(f'{digest}  {archive.name}\n', encoding='ascii')
    print(json.dumps(dict(archive=str(archive), exe=str(executable), bytes=archive.stat().st_size,
                          sha256=digest), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
