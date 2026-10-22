import threading
import unittest
from unittest.mock import Mock, patch

from backend.core.service import notify as notifications


class NotificationTests(unittest.TestCase):
    def test_non_windows_does_not_start_a_dialog(self):
        with patch.object(notifications.sys, 'platform', 'linux'), \
                patch.object(notifications, '_show_security_dialog') as dialog:
            self.assertFalse(notifications.notify_security_attention())
        dialog.assert_not_called()

    def test_reminder_is_nonblocking_deduplicated_and_releases_after_dismissal(self):
        entered, dismiss = threading.Event(), threading.Event()
        lock = threading.Lock()
        def dialog():
            entered.set()
            dismiss.wait(2)
        with patch.object(notifications.sys, 'platform', 'win32'), \
                patch.object(notifications, '_popup_lock', lock), \
                patch.object(notifications, '_show_security_dialog', side_effect=dialog):
            try:
                self.assertTrue(notifications.notify_security_attention())
                self.assertTrue(entered.wait(1))
                self.assertFalse(notifications.notify_security_attention())
            finally:
                dismiss.set()
                # Wait on the actual lock, rather than guessing thread timings.
                self.assertTrue(lock.acquire(timeout=2))
                lock.release()

    def test_native_dialog_uses_foreground_warning_and_explicit_manual_resume(self):
        api = Mock()
        api.MessageBoxW.return_value = 1
        with patch('ctypes.WinDLL', return_value=api, create=True):
            notifications._show_security_dialog()
        owner, message, title, flags = api.MessageBoxW.call_args.args
        self.assertIsNone(owner)
        self.assertIn('开始自动执行', message)
        self.assertIn('不会继续操作手机', message)
        self.assertIn('手工验证', title)
        self.assertEqual(flags, 0x30 | 0x10000 | 0x40000)

    def test_dialog_failure_releases_dedup_lock(self):
        lock = threading.Lock()
        with patch.object(notifications.sys, 'platform', 'win32'), \
                patch.object(notifications, '_popup_lock', lock), \
                patch.object(notifications, '_show_security_dialog', side_effect=OSError('no desktop')), \
                self.assertLogs('backend.core.service.notify', level='WARNING'):
            self.assertTrue(notifications.notify_security_attention())
            self.assertTrue(lock.acquire(timeout=2))
            lock.release()
