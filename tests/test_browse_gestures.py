import random
import threading
import unittest
from unittest.mock import Mock

from modules.browse_gestures import BrowseGestures
from modules.campaign import load_config, validate_config
from modules.windows_tray import WindowsTray


class GestureTests(unittest.TestCase):
    def test_distance_duration_positions_and_direction_bursts_stay_within_bounds(self):
        config = load_config()
        rng = BrowseGestures(config, random.Random(204))
        strokes = [rng.sample(1080, 2400) for _ in range(200)]
        directions = set()
        for x1, y1, x2, y2, duration in strokes:
            self.assertTrue(1080*.38 <= x1 <= 1080*.62)
            self.assertTrue(1080*.38 <= x2 <= 1080*.62)
            self.assertTrue(2400*.17 <= min(y1, y2) <= max(y1, y2) <= 2400*.87)
            self.assertTrue(.18-1/2400 <= abs(y2-y1)/2400 <= .36+1/2400)
            self.assertTrue(.25 <= duration <= .65)
            directions.add(y1 > y2)
        self.assertEqual(directions, {False, True})
        self.assertGreater(len(set(strokes)), 190)
        self.assertEqual(rng.interval(), 0)

    def test_max_distance_and_continuous_count_are_bounded_and_editable(self):
        config = load_config()
        config.update(swipe_distance_min=.5, swipe_distance_max=.5,
                      swipe_burst_min=2, swipe_burst_max=2,
                      swipe_interval_min=.2, swipe_interval_max=.3)
        validate_config(config)
        pattern = BrowseGestures(config, random.Random(3))
        strokes = [pattern.sample(400, 800) for _ in range(8)]
        self.assertEqual([a[1] > a[3] for a in strokes], [True, True, False, False]*2)
        self.assertTrue(all(abs(a[1]-a[3]) == 400 for a in strokes))
        self.assertTrue(.2 <= pattern.interval() <= .3)

    def test_invalid_reversed_nonfinite_or_fractional_burst_settings_are_rejected(self):
        for values in [dict(swipe_interval_min=1, swipe_interval_max=0), dict(swipe_duration_min=0),
                       dict(swipe_distance_max=.9), dict(swipe_burst_min=1.5),
                       dict(swipe_interval_max=float('nan')), dict(swipe_duration_max=True)]:
            config = load_config()
            config.update(values)
            with self.assertRaises(ValueError):
                validate_config(config)

    def test_tray_exit_callback_is_once_only_and_open_is_independent(self):
        opened, exited = threading.Event(), threading.Event()
        callback = Mock(side_effect=exited.set)
        tray = WindowsTray(opened.set, callback)
        tray.activate(1)
        self.assertTrue(opened.wait(1))
        tray.activate(2)
        tray.activate(2)
        self.assertTrue(exited.wait(1))
        callback.assert_called_once_with()
