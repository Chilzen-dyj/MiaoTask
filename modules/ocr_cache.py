"""Bounded recognition cache; text detection still runs on every fresh frame."""
from collections import OrderedDict
from dataclasses import replace
import hashlib
import threading
import time


class ExactTextCache:
    def __init__(self, recognize, capacity=512):
        self.recognize = recognize
        self.capacity = capacity
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        self.last_hits = self.last_misses = 0

    def __call__(self, args):
        # Character-box consumers have a different output contract. Leave those
        # calls untouched instead of caching results with incomplete geometry.
        if args.return_word_box or args.img is None:
            return self.recognize(args)
        images = args.img if isinstance(args.img, list) else [args.img]
        with self.lock:
            started = time.perf_counter()
            keys = [(im.shape, im.dtype.str, hashlib.sha256(im.tobytes()).digest()) for im in images]
            rows = [self.cache.get(key) for key in keys]
            missing = [i for i, value in enumerate(rows) if value is None]
            self.last_hits, self.last_misses = len(rows) - len(missing), len(missing)
            if missing:
                result = self.recognize(replace(args, img=[images[i] for i in missing]))
                if result.txts is None or len(result.txts) != len(missing):
                    return self.recognize(args)
                for j, i in enumerate(missing):
                    rows[i] = (result.txts[j], float(result.scores[j]))
                    self.cache[keys[i]] = rows[i]
            for key in keys:
                if key in self.cache:
                    self.cache.move_to_end(key)
            while len(self.cache) > self.capacity:
                self.cache.popitem(last=False)
            from rapidocr.ch_ppocr_rec import TextRecOutput
            return TextRecOutput(imgs=images, txts=tuple(row[0] for row in rows),
                                 scores=tuple(row[1] for row in rows),
                                 word_results=tuple(None for _ in rows),
                                 elapse=time.perf_counter() - started)
