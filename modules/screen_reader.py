"""Prefer readable controls; visual verification skips redundant hierarchy RPCs."""
import copy
from dataclasses import dataclass
from functools import lru_cache
import hashlib
import logging
import re
import time

from modules.task_model import TextNode, bounds_of, normalize

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def local_ocr_engine():
    try:
        from rapidocr import RapidOCR
    except ImportError as exc:
        raise RuntimeError('页面未提供可读控件，请先运行 pip install -r requirements.txt 安装本地 OCR') from exc
    return RapidOCR(params={
        'EngineConfig.onnxruntime.intra_op_num_threads': 2,
        'EngineConfig.onnxruntime.inter_op_num_threads': 2,
        'Global.log_level': 'warning',
    })


@dataclass
class Screen:
    nodes: list
    width: int
    height: int
    package: str
    source: str = "ui"
    tree: object = None

    @property
    def text(self):
        return "\n".join(n.text for n in self.nodes)

    def find(self, pattern, exact=False):
        for node in self.nodes:
            if (normalize(node.text) == normalize(pattern) if exact else
                    re.search(pattern, normalize(node.text))):
                return node
        return None


class ScreenReader:
    def __init__(self, device, ocr=True, on_image=None):
        self.device = device
        self.ocr_enabled = ocr
        self.on_image = on_image
        self._engine = None
        self._ocr_notice = False
        self._size = None
        self.last_image = None
        self.last_screen = None
        self._last_preview = 0
        self._ocr_cache_key = None
        self._ocr_cache_nodes = None
        self.last_observation_seconds = 0.0

    def _flatten(self, tree):
        nodes = []
        def walk(item):
            if isinstance(item, list):
                for child in item:
                    walk(child)
            elif isinstance(item, dict):
                attrs = item.get("attributes", item)
                package = attrs.get("package", "")
                if not package.startswith(("com.android.systemui", "com.miui.notes", "com.google.android.inputmethod")):
                    text = attrs.get("text") or attrs.get("description") or attrs.get("content-desc") or ""
                    bounds = bounds_of(attrs.get("bounds", attrs.get("rect")))
                    if text and bounds[2] > bounds[0] and bounds[3] > bounds[1]:
                        nodes.append(TextNode(text, bounds))
                for key in ("children", "hierarchy"):
                    if isinstance(item.get(key), (list, dict)):
                        walk(item[key])
        walk(tree)
        return nodes

    def _ocr(self, image):
        if self._engine is None:
            self._engine = local_ocr_engine()
        import numpy as np
        # Limit image width to reduce CPU work, then map boxes back to the phone.
        scale = min(1.0, 1000 / image.width)
        resized = image.resize((round(image.width * scale), round(image.height * scale)))
        result = self._engine(np.asarray(resized), use_cls=False)
        results = zip(result.boxes, result.txts, result.scores) if result.boxes is not None else []
        nodes = []
        for box, text, confidence in results:
            if confidence < .65:
                continue
            xs, ys = zip(*box)
            bounds = tuple(round(v / scale) for v in (min(xs), min(ys), max(xs), max(ys)))
            nodes.append(TextNode(text, bounds, "ocr"))
        return nodes

    def _image_nodes(self, image):
        # Include every original RGB pixel and the dimensions. A thumbnail or
        # perceptual hash can miss a changed countdown or modal and is unsafe.
        key = (image.size, hashlib.sha256(image.tobytes()).digest())
        if key == self._ocr_cache_key:
            return copy.deepcopy(self._ocr_cache_nodes)
        nodes = self._ocr(image)
        self._ocr_cache_key = key
        self._ocr_cache_nodes = copy.deepcopy(nodes)
        return nodes

    def _capture(self):
        image = self.device.screenshot().convert('RGB')
        self.last_image = image
        self._size = image.size
        if self.on_image:
            self.on_image(image)
        self._last_preview = time.monotonic()
        return image

    def read(self, force_ocr=False):
        started = time.monotonic()
        direct_visual = bool(force_ocr and self.ocr_enabled)
        tree = None if direct_visual else self.device.dump_hierarchy()
        package = self.device.current_app().get("package", "")
        nodes = [] if direct_visual else self._flatten(tree)
        meaningful = [n for n in nodes if n.bounds[3] - n.bounds[1] < (self._size or (1440, 3200))[1] * .4]
        source = "ui"
        if self.ocr_enabled and (force_ocr or len(meaningful) < 5):
            if not self._ocr_notice:
                logger.info("页面控件不可读，启用本地 OCR 识别（截图不上传）")
                self._ocr_notice = True
            image = self._capture()
            nodes = self._image_nodes(image)
            source = "ocr"
        elif (self.on_image and not getattr(self.device, 'preview_managed', False)
              and time.monotonic() - self._last_preview >= 1):
            self._capture()
        if self._size is None:
            self._size = self.device.display_size
        screen = Screen(nodes, *self._size, package, source, tree)
        self.last_screen = screen
        self.last_observation_seconds = time.monotonic() - started
        return screen
