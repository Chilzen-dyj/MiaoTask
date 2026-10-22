"""Distribution notices must survive packaging regardless of wheel layout."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from scripts.package_windows import copy_documentation, licenses, ROOT


class PackageLicenseTests(unittest.TestCase):
    def distribution(self, root, name, files, version='1.0'):
        for relative in files:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('Original notice: ' + relative, encoding='utf-8')
        return SimpleNamespace(metadata={'Name': name}, files=files,
                               version=version, locate_file=lambda path: root / path)

    def test_package_local_and_british_spelled_notices_are_retained(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            dists = [
                self.distribution(root, 'onnxruntime',
                                  ['onnxruntime/LICENSE', 'onnxruntime/ThirdPartyNotices.txt']),
                self.distribution(root, 'tqdm', ['tqdm-1.0.dist-info/licenses/LICENCE']),
            ]
            (root / 'NOTICE.txt').write_text('ADB notice', encoding='utf-8')
            with patch('scripts.package_windows.metadata.distributions', return_value=dists):
                licenses(root / 'output', root)
            for dist in dists:
                for relative in dist.files:
                    self.assertEqual((root / 'output' / dist.metadata['Name'] / relative).read_bytes(),
                                     (root / relative).read_bytes())
            self.assertEqual((root / 'output/Android-platform-tools-NOTICE.txt').read_text(), 'ADB notice')

    def test_project_license_scope_is_present_in_help_and_licenses(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            copy_documentation(root)
            (root / 'NOTICE.txt').write_text('ADB notice', encoding='utf-8')
            with patch('scripts.package_windows.metadata.distributions', return_value=[]):
                licenses(root / 'licenses', root)
            for name in ('LICENSE', 'NOTICE'):
                for target in (root / name, root / 'licenses/MiaoTask' / name):
                    self.assertEqual(target.read_bytes(), (ROOT / name).read_bytes())
            self.assertEqual((root / 'docs/LICENSING.md').read_bytes(),
                             (ROOT / 'docs/LICENSING.md').read_bytes())

    def test_flatbuffers_notice_is_version_bound_and_keeps_copyright(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            (root / 'NOTICE.txt').write_text('ADB notice', encoding='utf-8')
            dist = self.distribution(root, 'flatbuffers', [], version='25.12.19')
            with patch('scripts.package_windows.metadata.distributions', return_value=[dist]):
                licenses(root / 'output', root)
            self.assertEqual((root / 'output/flatbuffers/LICENSE').read_bytes(), (ROOT / 'LICENSE').read_bytes())
            notice = (root / 'output/flatbuffers/NOTICE.txt').read_text(encoding='utf-8')
            self.assertIn('Copyright 2014 Google Inc.', notice)
            self.assertIn('/v25.12.19/', notice)

    def test_new_flatbuffers_without_a_license_requires_review(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            dist = self.distribution(root, 'flatbuffers', [], version='99.0.0')
            with patch('scripts.package_windows.metadata.distributions', return_value=[dist]):
                with self.assertRaisesRegex(RuntimeError, 'Review the FlatBuffers license'):
                    licenses(root / 'output', root)

    def test_license_directory_does_not_copy_code_bytecode_or_binaries(self):
        with tempfile.TemporaryDirectory() as work:
            root = Path(work)
            declaration_files = [
                'packaging-1.0.dist-info/licenses/LICENSE',
                'packaging-1.0.dist-info/licenses/LICENSE.APACHE',
                'packaging-1.0.dist-info/licenses/AUTHORS.txt',
                'rapidocr-1.0.dist-info/licenses/MODEL_LICENSES.md',
                'runtime/COPYING', 'runtime/ThirdPartyNotices.txt',
            ]
            excluded = [
                'packaging/licenses/__init__.py',
                'packaging/licenses/_spdx.py',
                'packaging/licenses/__pycache__/__init__.cpython-313.pyc',
                'pip/_vendor/packaging/licenses/_spdx.py',
                'packaging-1.0.dist-info/licenses/helper.py',
                'packaging-1.0.dist-info/licenses/README.md',
                'runtime/LICENSE.py', 'runtime/LICENSE.pyd',
                'runtime/LICENSE.dll', 'runtime/NOTICE.exe',
                'runtime/COPYING.pyc', 'runtime/LICENSE.txt',
            ]
            dist = self.distribution(root, 'sample', declaration_files + excluded)
            (root / 'runtime/LICENSE.txt').write_bytes(b'MZ\0Binary payload')
            (root / 'NOTICE.txt').write_text('ADB notice', encoding='utf-8')
            with patch('scripts.package_windows.metadata.distributions', return_value=[dist]):
                licenses(root / 'output', root)
            copied = {p.relative_to(root / 'output/sample').as_posix()
                      for p in (root / 'output/sample').rglob('*') if p.is_file()}
            self.assertEqual(copied, set(declaration_files))


if __name__ == '__main__':
    unittest.main()
