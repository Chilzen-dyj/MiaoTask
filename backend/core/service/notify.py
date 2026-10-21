"""Non-blocking Windows reminder for a stopped security challenge."""
import logging
import sys
import threading

logger = logging.getLogger(__name__)
_popup_lock = threading.Lock()


def _show_security_dialog():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    dialog = user32.MessageBoxW
    dialog.argtypes = [wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT]
    dialog.restype = ctypes.c_int
    # OK + warning icon + foreground + topmost. Closing this reminder does not
    # authorize any phone action, resume the worker, or solve the challenge.
    result = dialog(None,
                    '手机页面出现安全验证，喵任务已停止自动操作并保存失败现场。\n\n'
                    '请解锁手机，由本人完成滑块或图片等验证。\n'
                    '处理完成后，回到网页控制台点击「开始自动执行」。\n\n'
                    '点击「确定」只关闭此提醒，不会继续操作手机。',
                    '喵任务 · 请在手机上手工验证', 0x30 | 0x10000 | 0x40000)
    if result == 0:
        raise ctypes.WinError(ctypes.get_last_error())


def notify_security_attention():
    """One visible reminder at a time, without blocking the server or exit."""
    if sys.platform != 'win32' or not _popup_lock.acquire(blocking=False):
        return False

    def show():
        try:
            _show_security_dialog()
        except Exception:
            logger.warning('Windows 提醒未能显示，请查看网页中的安全验证提示', exc_info=True)
        finally:
            _popup_lock.release()

    worker = threading.Thread(target=show, name='security-reminder', daemon=True)
    try:
        worker.start()
    except Exception:
        _popup_lock.release()
        raise
    return True
