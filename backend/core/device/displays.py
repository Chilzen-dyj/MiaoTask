"""Logical Android display targets and SurfaceFlinger capture identifiers."""
import re


def focused_display(window_dump):
    match = re.search(r'mTopFocusedDisplayId\s*=\s*(\d+)', window_dump)
    return int(match[1]) if match else 0


def focused_window_dump(displays_dump, logical_id):
    for block in re.split(r'(?=^\s*Display: mDisplayId=)', displays_dump, flags=re.M):
        match=re.search(r'Display: mDisplayId=(\d+)',block)
        if match and int(match[1])==logical_id:
            return block
    return ''


def capture_display(display_dump, logical_id):
    # Logical ID, HWC port and adbutils ordinal are three different namespaces.
    # Resolve through Android's explicit primary-device uniqueId mapping.
    pattern = r'mDisplayId=' + str(int(logical_id)) + r'\s+mPrimaryDisplayDevice=[^\n]*\(local:(\d+)\)'
    match = re.search(pattern, display_dump)
    if match:
        return match[1]
    raise RuntimeError('无法映射当前应用屏幕，已停止截图和点击；请检查模拟器多屏状态')
