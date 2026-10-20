import unittest
from unittest.mock import Mock

from PIL import Image

from modules.campaign import CampaignRunner, NeedsAttention
from modules.screen_reader import Screen, ScreenReader
from modules.task_model import TextNode


class RegionOCRTests(unittest.TestCase):
    def test_crop_maps_coordinates_and_keeps_full_frame_security_context(self):
        reader = ScreenReader(Mock())
        screen = Screen([TextNode('请完成安全验证', (10, 10, 300, 70))],
                        1440, 3200, 'com.taobao.taobao', 'ocr')
        reader.last_screen = screen
        reader.last_image = Image.new('RGB', (1440, 3200))
        reader._ocr = Mock(return_value=[TextNode('去赚能量', (20, 30, 180, 80))])
        enriched = reader.enrich_regions(screen, [(1000, 1100, 1440, 1400)])
        self.assertEqual(enriched.nodes[-1].bounds, (1020, 1130, 1180, 1180))
        self.assertIn(screen.nodes[0], enriched.nodes)
        reader.device.screenshot.assert_not_called()
        runner = CampaignRunner(Mock())
        with self.assertRaises(NeedsAttention) as raised:
            runner.guard(enriched)
        self.assertEqual(raised.exception.kind, 'security')

    def test_crop_never_reuses_pixels_from_a_different_observation(self):
        reader = ScreenReader(Mock())
        screen = Screen([], 1440, 3200, 'com.taobao.taobao', 'ocr')
        reader.last_screen = Screen([], 1440, 3200, 'com.taobao.taobao', 'ocr')
        reader.last_image = Image.new('RGB', (1440, 3200))
        reader._ocr = Mock()
        self.assertIs(reader.enrich_regions(screen, [(1000, 1100, 1440, 1400)]), screen)
        reader._ocr.assert_not_called()

    def test_region_bounds_are_clamped_to_current_frame(self):
        reader = ScreenReader(Mock())
        screen = Screen([], 1440, 3200, 'com.taobao.taobao', 'ocr')
        reader.last_screen = screen
        reader.last_image = Image.new('RGB', (1440, 3200))
        sizes = []
        reader._ocr = Mock(side_effect=lambda image: sizes.append(image.size) or [])
        reader.enrich_regions(screen, [(-20, -30, 1500, 3300), (1500, 0, 1600, 50)])
        self.assertEqual(sizes, [(1440, 3200)])
