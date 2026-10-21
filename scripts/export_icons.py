"""Export requested platform sizes from the single AI-generated icon master.

Only resampling and format conversion; no redraw or changes to the artwork.
"""
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parent.parent
PNG_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 180, 256, 512, 1024)
ICO_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 256)


def export_icons(folder=None):
    folder = Path(folder or ROOT / 'frontend/assets')
    with Image.open(folder / 'miaotask-master.png') as master:
        master = master.convert('RGBA')
        if master.width != master.height:
            raise ValueError('Icon master must be square')
        for size in PNG_SIZES:
            master.resize((size, size), Image.Resampling.LANCZOS).save(
                folder / f'miaotask-{size}.png', optimize=True)
        master.save(folder / 'miaotask.ico', format='ICO', sizes=[(s, s) for s in ICO_SIZES])
    return [f'miaotask-{size}.png' for size in PNG_SIZES] + ['miaotask.ico']


if __name__ == '__main__':
    print('\n'.join(export_icons()))
