"""Download Google's platform tools and extract only the ADB runtime/notice."""
import argparse
import hashlib
import io
from pathlib import Path, PurePosixPath
from urllib.request import urlopen
import zipfile

URL = 'https://dl.google.com/android/repository/platform-tools-latest-windows.zip'
FILES = {'adb.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll', 'libwinpthread-1.dll',
         'NOTICE.txt', 'source.properties'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='build/vendor/platform-tools')
    args = parser.parse_args()
    folder = Path(args.output).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    with urlopen(URL, timeout=120) as response:
        data = response.read()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for entry in archive.infolist():
            path = PurePosixPath(entry.filename.replace('\\', '/'))
            if path.is_absolute() or '..' in path.parts or ':' in entry.filename:
                raise RuntimeError('Unsafe archive path')
            if path.parts == ('platform-tools', path.name) and path.name in FILES:
                (folder / path.name).write_bytes(archive.read(entry))
    if not all((folder / name).is_file() for name in ('adb.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll', 'NOTICE.txt')):
        raise RuntimeError('The ADB distribution is incomplete')
    print(f'ADB runtime: {folder}; source archive SHA256: {hashlib.sha256(data).hexdigest()}')


if __name__ == '__main__':
    main()
