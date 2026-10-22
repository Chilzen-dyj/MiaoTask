"""Review preparation is separate from building and publishing."""
import json
from pathlib import Path
import tempfile
import unittest
import yaml
from scripts.prepare_release import prepare, pending_entries
from scripts.release_notes import extract_notes


class ReleasePreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'docs').mkdir()
        (self.root / 'version.json').write_text(json.dumps({'version':'MiaoTask-v0.0.9','app_version':'MiaoTask-v0.0.9'}))
        (self.root / 'docs/UNRELEASED.md').write_text('# 待发布贡献\n\n## 待发布\n\n* 【修复】合成问题 (#10)\n* 【新增】合成能力 (#11)\n', encoding='utf-8')
        (self.root / 'docs/RELEASES.md').write_text('# 发布记录\n\n说明。\n\n## MiaoTask-v0.0.9\n\n旧说明。\n', encoding='utf-8')

    def test_rollup_keeps_history_resets_accumulator_and_updates_both_versions(self):
        prepare(self.root, 'MiaoTask-v0.1.0', '合成更新。')
        history = (self.root / 'docs/RELEASES.md').read_text(encoding='utf-8')
        self.assertIn('合成能力 (#11)', extract_notes(history, 'MiaoTask-v0.1.0'))
        self.assertEqual(extract_notes(history, 'MiaoTask-v0.0.9'), '旧说明。\n')
        self.assertEqual(pending_entries((self.root / 'docs/UNRELEASED.md').read_text(encoding='utf-8')), [])
        metadata = json.loads((self.root / 'version.json').read_text())
        self.assertEqual(metadata['version'], metadata['app_version'])
        self.assertEqual(metadata['version'], 'MiaoTask-v0.1.0')

    def test_invalid_existing_and_backwards_version_do_not_change_files(self):
        paths = list(self.root.rglob('*.md')) + [self.root / 'version.json']
        before = {path:path.read_bytes() for path in paths}
        for version in ('MiaoTask-v0.0.9', 'MiaoTask-v0.0.8', 'v0.1.0', 'MiaoTask-v1.0.0'):
            with self.assertRaises(ValueError):
                prepare(self.root, version, '更新')
            self.assertEqual(before, {path:path.read_bytes() for path in paths})

    def test_invalid_pending_entries_and_empty_release_fail(self):
        with self.assertRaises(ValueError):
            pending_entries('## 待发布\n* unrelated text\n')
        (self.root / 'docs/UNRELEASED.md').write_text('## 待发布\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            prepare(self.root, 'MiaoTask-v0.1.0', '更新')

    def test_pr_and_tag_events_never_build_or_publish(self):
        folder = Path(__file__).resolve().parents[1] / '.github/workflows'
        # BaseLoader preserves YAML's `on` key instead of YAML 1.1 booleans.
        for name in ('prepare-release.yml', 'release.yml', 'publish-release.yml'):
            workflow = yaml.load((folder / name).read_text(encoding='utf-8'), Loader=yaml.BaseLoader)
            self.assertEqual(set(workflow['on']), {'workflow_dispatch'})
        ci = (folder / 'ci.yml').read_text(encoding='utf-8')
        self.assertNotIn('package_windows.py', ci)
        self.assertNotIn('gh release', ci)
        self.assertNotIn('contents: write', ci)


if __name__ == '__main__':
    unittest.main()
