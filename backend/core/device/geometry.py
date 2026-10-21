"""Image-to-device coordinates; identity is the unchanged default path."""
from dataclasses import dataclass
from typing import Protocol
import re


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

    @property
    def content_bounds(self):
        left, top, right, bottom = self.safe_insets
        return left, top, self.width-right, self.height-bottom

    def contains(self, x, y):
        left, top, right, bottom = self.content_bounds
        return left <= x < right and top <= y < bottom and not any(a <= x < c and b <= y < d for a,b,c,d in self.cutouts)


def geometry_from_window(width, height, output):
    """Use reported edge bars/cutouts; absence of metadata preserves full bounds."""
    insets = [0,0,0,0]
    for kind, a,b,c,d,visible in re.findall(r'type=(statusBars|navigationBars) frame=\[(\d+),(\d+)\]\[(\d+),(\d+)\] visible=(true|false)', output):
        a,b,c,d = map(int,(a,b,c,d))
        if visible != 'true' or c > width or d > height:
            continue
        if a == 0 and c == width and b == 0 and d < height*.15: insets[1]=max(insets[1],d)
        if a == 0 and c == width and d == height and b > height*.8: insets[3]=max(insets[3],height-b)
        if b == 0 and d == height and a == 0 and c < width*.1: insets[0]=max(insets[0],c)
        if b == 0 and d == height and c == width and a > width*.9: insets[2]=max(insets[2],width-a)
    cutouts=[]
    for chunk in re.findall(r'boundingRect=\{Bounds=\[(.*?)\]\}', output):
        for values in re.findall(r'Rect\((\d+), (\d+) - (\d+), (\d+)\)',chunk):
            box=tuple(map(int,values))
            if 0 <= box[0] < box[2] <= width and 0 <= box[1] < box[3] <= height: cutouts.append(box)
    return DisplayGeometry(width,height,safe_insets=tuple(insets),cutouts=tuple(cutouts))


def ocr_tiles(image):
    """Wide screens retain readable text size; portrait OCR keeps its old path."""
    if image.width <= 1400 or image.width <= image.height * 1.15:
        return [(image,0,0)]
    count = (image.width+999)//1000
    starts = [round(i*(image.width-1100)/(count-1)) for i in range(count)]
    return [(image.crop((x,0,min(image.width,x+1100),image.height)),x,0) for x in starts]


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
