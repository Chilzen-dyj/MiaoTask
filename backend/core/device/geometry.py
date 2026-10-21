"""Image-to-device coordinates; identity is the unchanged default path."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class DisplayGeometry:
    width: int
    height: int
    rotation: int = 0
    safe_insets: tuple = (0, 0, 0, 0)
    cutouts: tuple = ()

    def __post_init__(self):
        if self.width <= 0 or self.height <= 0 or self.rotation not in (0, 90, 180, 270):
            raise ValueError('屏幕尺寸或方向无效')
        left, top, right, bottom = self.safe_insets
        if min(self.safe_insets) < 0 or left + right >= self.width or top + bottom >= self.height:
            raise ValueError('屏幕安全区域无效')


@dataclass(frozen=True)
class CoordinateTransform:
    scale_x: float = 1
    scale_y: float = 1
    offset_x: float = 0
    offset_y: float = 0

    def __post_init__(self):
        if self.scale_x <= 0 or self.scale_y <= 0:
            raise ValueError('坐标缩放系数必须为正数')

    def point(self, x, y):
        return round(x * self.scale_x + self.offset_x), round(y * self.scale_y + self.offset_y)

    def bounds(self, box):
        return (*self.point(box[0], box[1]), *self.point(box[2], box[3]))


@dataclass(frozen=True)
class PreparedImage:
    image: object
    to_device: CoordinateTransform = CoordinateTransform()


class ImageProcessor(Protocol):
    cache_key: object
    def prepare(self, image) -> PreparedImage: ...


class IdentityImageProcessor:
    cache_key = ('identity',)

    def prepare(self, image):
        return PreparedImage(image)
