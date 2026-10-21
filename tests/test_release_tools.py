import json
from pathlib import Path
import re
import tempfile
import unittest

from scripts.package_windows import copy_documentation, PORTABLE_DOCS
from scripts.release_notes import extract_notes, ROOT


class ReleaseNotesTests(unittest.TestCase):
    def test_only_requested_version_is_extracted_including_subheadings(self):
        text = '# Releases\r\n\r\n## v2\r\nNew behavior\r\n### Details\r\nKeep these\r\n\r\n## v1\r\nOld behavior\r\n'
        body = extract_notes(text, 'v2')
        self.assertIn('New behavior', body)
        self.assertIn('### Details', body)
        self.assertNotIn('Old behavior', body)
        self.assertEqual(extract_notes(text, 'v1'), 'Old behavior\n')

    def test_missing_duplicate_empty_and_invalid_versions_are_rejected(self):
        cases = [
            ('## v2\nNew\n', 'v1'),
            ('## v1\nFirst\n## v1\nSecond\n', 'v1'),
            ('## v1\n\n## v2\nOther\n', 'v1'),
            ('## v1\nBody\n', '../v1'),
        ]
        for text, version in cases:
            with self.subTest(version=version), self.assertRaises(ValueError):
                extract_notes(text, version)

    def test_configured_version_has_a_single_reviewable_release_section(self):
        version = json.loads((ROOT / 'version.json').read_text(encoding='utf-8'))['version']
        notes = extract_notes((ROOT / 'docs/RELEASES.md').read_text(encoding='utf-8'), version)
        self.assertIn('MiaoTask', notes)


class PortableDocsTests(unittest.TestCase):
    def test_packaged_help_uses_current_docs_and_all_local_links_resolve(self):
        with tempfile.TemporaryDirectory() as work:
            destination = Path(work)
            copy_documentation(destination)
            self.assertEqual({p.name for p in (destination / 'docs').iterdir()}, set(PORTABLE_DOCS))
            for name in PORTABLE_DOCS:
                self.assertEqual((destination / 'docs' / name).read_bytes(), (ROOT / 'docs' / name).read_bytes())
            for file in destination.rglob('*.md'):
                for link in re.findall(r'\]\(([^\s)]+)\)', file.read_text(encoding='utf-8')):
                    if '://' not in link and not link.startswith('#'):
                        self.assertTrue((file.parent / link.split('#')[0]).is_file(), (file.name, link))


if __name__ == '__main__':
    unittest.main()
