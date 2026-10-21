"""Extract one reviewed release section from the shared project changelog."""
import argparse
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent


def extract_notes(text, version):
    if not re.fullmatch(r'v[A-Za-z0-9._-]+', version):
        raise ValueError('Invalid version')
    sections = list(re.finditer(r'^##[ \t]+([^\r\n]+)[ \t]*\r?$', text, re.M))
    matches = [index for index, item in enumerate(sections) if item.group(1).strip() == version]
    if len(matches) != 1:
        raise ValueError('Expected exactly one release section for this version')
    index = matches[0]
    end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
    body = text[sections[index].end():end].strip()
    if not body:
        raise ValueError('Release notes must not be empty')
    return body + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('version')
    parser.add_argument('--source', type=Path, default=ROOT / 'docs/RELEASES.md')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        notes = extract_notes(args.source.read_text(encoding='utf-8-sig'), args.version)
    except ValueError as exc:
        parser.error(str(exc))
    args.output.write_text(notes, encoding='utf-8')


if __name__ == '__main__':
    main()
