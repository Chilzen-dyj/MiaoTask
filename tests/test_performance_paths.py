import threading
import unittest
from unittest.mock import Mock, patch

import numpy as np
from PIL import Image
from rapidocr.ch_ppocr_rec import TextRecInput, TextRecOutput

from modules.device_adapter import DeviceAdapter
from modules.ocr_cache import ExactTextCache


class ExactTextCacheTests(unittest.TestCase):
    def backend(self):
        return Mock(side_effect=lambda args: TextRecOutput(
            imgs=args.img, txts=tuple(str(int(im.flat[0])) for im in args.img),
            scores=tuple(.99 for _ in args.img), word_results=tuple(None for _ in args.img)))

    def test_unchanged_text_is_reused_but_one_pixel_change_is_recognized(self):
        backend = self.backend()
        cache = ExactTextCache(backend)
        first = np.zeros((8, 20, 3), dtype=np.uint8)
        cache(TextRecInput(img=[first]))
        same = cache(TextRecInput(img=[first.copy()]))
        self.assertEqual(same.txts, ('0',))
        self.assertEqual(backend.call_count, 1)
        changed = first.copy()
        changed[0, 0, 0] = 7
        result = cache(TextRecInput(img=[first, changed]))
        self.assertEqual(result.txts, ('0', '7'))
        self.assertEqual(len(backend.call_args.args[0].img), 1)
        self.assertEqual((cache.last_hits, cache.last_misses), (1, 1))

    def test_equal_bytes_with_different_geometry_are_not_reused(self):
        backend = self.backend()
        cache = ExactTextCache(backend)
        cache(TextRecInput(img=[np.zeros((8, 20, 3), dtype=np.uint8)]))
        cache(TextRecInput(img=[np.zeros((20, 8, 3), dtype=np.uint8)]))
        self.assertEqual(backend.call_count, 2)

    def test_cache_is_bounded_and_word_geometry_requests_bypass_it(self):
        backend = self.backend()
        cache = ExactTextCache(backend, capacity=2)
        images = [np.full((8, 20, 3), i, dtype=np.uint8) for i in range(3)]
        cache(TextRecInput(img=images))
        self.assertEqual(len(cache.cache), 2)
        cache(TextRecInput(img=[images[0]]))
        self.assertEqual(cache.last_misses, 1)
        cache(TextRecInput(img=[images[0]], return_word_box=True))
        self.assertTrue(backend.call_args.args[0].return_word_box)


class FreshFrameTests(unittest.TestCase):
    def adapter(self):
        adapter = DeviceAdapter.__new__(DeviceAdapter)
        adapter.device_type = 'uiautomator2'
        adapter.io_lock = threading.RLock()
        adapter._device = Mock()
        adapter._device.screenshot.return_value = Image.new('RGB', (40, 80), 'white')
        return adapter

    def test_near_simultaneous_preview_and_ocr_share_one_frame_without_aliasing(self):
        phone = self.adapter()
        with patch('modules.device_adapter.time.monotonic', return_value=10):
            phone.screenshot()
        with patch('modules.device_adapter.time.monotonic', return_value=10.1):
            image = phone.screenshot(max_age=.15)
            image.putpixel((0, 0), (0, 0, 0))
            self.assertEqual(phone.screenshot(max_age=.15).getpixel((0, 0)), (255, 255, 255))
        self.assertEqual(phone._device.screenshot.call_count, 1)

    def test_expired_frames_and_failure_evidence_always_capture_again(self):
        phone = self.adapter()
        with patch('modules.device_adapter.time.monotonic', return_value=10):
            phone.screenshot()
        with patch('modules.device_adapter.time.monotonic', return_value=10.2):
            phone.screenshot(max_age=5)
            phone.screenshot()
        self.assertEqual(phone._device.screenshot.call_count, 3)

    def test_input_and_failed_input_invalidate_shared_frames(self):
        phone = self.adapter()
        with patch('modules.device_adapter.time.monotonic', return_value=10):
            phone.screenshot()
            phone.click(20, 30)
            phone.screenshot(max_age=.15)
            phone._device.press.side_effect = OSError('input failed')
            with self.assertRaises(OSError):
                phone.go_back()
            phone.screenshot(max_age=.15)
        self.assertEqual(phone._device.screenshot.call_count, 3)

    def test_foreground_switch_invalidates_cached_frame(self):
        phone = self.adapter()
        phone._device.app_current.return_value = {'package': 'com.taobao.taobao'}
        phone.current_app()
        with patch('modules.device_adapter.time.monotonic', return_value=10):
            phone.screenshot()
            phone._device.app_current.return_value = {'package': 'com.example.other'}
            phone.current_app()
            phone.screenshot(max_age=.15)
        self.assertEqual(phone._device.screenshot.call_count, 2)
