"""Structural driver seam for future native, remote and emulator backends."""
from typing import Protocol, runtime_checkable


@runtime_checkable
class DeviceBackend(Protocol):
    device_type: str

    @property
    def display_size(self) -> tuple[int, int]: ...
    def current_app(self) -> dict: ...
    def dump_hierarchy(self) -> dict: ...
    def screenshot(self, max_age: float = 0): ...
    def click(self, x: int, y: int): ...
    def swipe(self, x1, y1, x2, y2, duration=0.5): ...
    def go_back(self): ...
    def go_home(self): ...
    def input_text(self, text: str): ...
    def press(self, key: str): ...


class DriverFactory:
    def __init__(self):
        self._factories = {}

    def register(self, name, factory):
        if name in self._factories:
            raise ValueError('驱动已注册')
        self._factories[name] = factory

    def create(self, name, **kwargs):
        if name not in self._factories:
            raise ValueError('未注册设备驱动')
        return self._factories[name](**kwargs)
