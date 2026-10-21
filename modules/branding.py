"""The reviewed application icon resources shared by web and Windows builds."""
from modules.runtime import assets_dir


ICON_SIZES = (16, 20, 24, 32, 40, 48, 64, 128, 180, 256, 512, 1024)
PUBLIC_ICON_FILES = frozenset(f'miaotask-{size}.png' for size in ICON_SIZES) | {'miaotask.ico'}


def windows_icon_path():
    return assets_dir() / 'web/assets/miaotask.ico'
