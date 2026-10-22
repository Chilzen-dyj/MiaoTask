"""Roll reviewed pending contributions into the unified release history."""
import argparse
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent
MARKER = '## 待发布\n'
CATEGORIES = ('新增', '优化', '修复', '文档', '维护')


def pending_entries(text):
    if text.count(MARKER) != 1:
        raise ValueError('UNRELEASED.md must contain exactly one pending section')
    body = text.split(MARKER, 1)[1]
    entries = []
    for line in body.splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'\* 【(新增|优化|修复|文档|维护)】([^\r\n]+)', line)
        if not match:
            raise ValueError('Pending entries must use * 【分类】说明 (#PR) on one line')
        entries.append((match[1], match[2].strip()))
    return entries


def prepare(root, version, summary):
    if not re.fullmatch(r'MiaoTask-v0\.\d+\.\d+', version):
        raise ValueError('Expected MiaoTask-v0.x.y')
    if not summary.strip() or '\n' in summary or '\r' in summary or len(summary) > 100:
        raise ValueError('Use a short, single-line release summary')
    root = Path(root)
    pending_path, history_path = root / 'docs/UNRELEASED.md', root / 'docs/RELEASES.md'
    pending = pending_path.read_text(encoding='utf-8-sig')
    entries = pending_entries(pending)
    if not entries:
        raise ValueError('No pending contributions')
    history = history_path.read_text(encoding='utf-8-sig')
    if re.search(r'^## ' + re.escape(version) + r'\s*$', history, re.M):
        raise ValueError('Version already exists; do not overwrite release history')
    metadata_path = root / 'version.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8-sig'))
    current = metadata.get('version', '')
    def numbers(value):
        return tuple(map(int, value.removeprefix('MiaoTask-v').split('.')))
    if not re.fullmatch(r'MiaoTask-v0\.\d+\.\d+', current) or numbers(version) < numbers(current):
        raise ValueError('Version must not go backwards')
    groups = []
    for category in CATEGORIES:
        values = [value for kind, value in entries if kind == category]
        if values:
            groups.append('* 【' + category + '】' + '；'.join(value.rstrip('。；') for value in values) + '。')
    footer = ('下载 Windows x64 ZIP，完整解压后运行 `MiaoTask.exe`，保留 `_internal/`。升级前退出旧助手。'
              '安全认证需本人处理，诊断截图分享前请脱敏。\n\n'
              '基于 [MonsterNone/tmall-miao next](https://github.com/MonsterNone/tmall-miao) 改造。'
              '[使用说明](https://github.com/h0ll0w-AkuZr0guY/tmall-miao-double11/blob/main/docs/USAGE.md) · '
              '[项目介绍](https://github.com/h0ll0w-AkuZr0guY/tmall-miao-double11#readme)\n\n')
    section = '## ' + version + '\n\n' + summary.strip() + '\n\n' + '\n'.join(groups) + '\n\n' + footer
    position = re.search(r'^## ', history, re.M)
    position = position.start() if position else len(history.rstrip()) + 2
    if position > len(history):
        history = history.rstrip() + '\n\n'
        position = len(history)
    metadata.update(version=version, app_version=version)
    # Validate all inputs before changing any of the three reviewable files.
    history_path.write_text(history[:position] + section + history[position:], encoding='utf-8')
    pending_path.write_text(pending.split(MARKER, 1)[0] + MARKER, encoding='utf-8')
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version')
    parser.add_argument('--summary')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    try:
        if args.check:
            pending_entries((ROOT / 'docs/UNRELEASED.md').read_text(encoding='utf-8-sig'))
        else:
            if not args.version or not args.summary:
                parser.error('--version and --summary are required')
            prepare(ROOT, args.version, args.summary)
    except (ValueError, OSError) as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
