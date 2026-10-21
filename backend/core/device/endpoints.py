"""Explicit ADB endpoints; emulator discovery must supply actual configured ports."""
from dataclasses import dataclass
import ipaddress
from typing import Protocol


@dataclass(frozen=True)
class DeviceEndpoint:
    serial: str
    driver: str = 'uiautomator2'
    transport: str = 'usb'
    label: str = ''


class EndpointProvider(Protocol):
    def discover(self) -> list[DeviceEndpoint]: ...


class ConfiguredEmulatorProvider:
    """MuMu and other emulators use the existing ADB TCP connection path.

    No guessed ports, emulator launch, adb-server restart or silent device choice.
    A future vendor provider may read its configured instance ports and feed this.
    """
    def __init__(self, addresses, label='Android 模拟器'):
        self.endpoints = []
        for address in addresses:
            host, port = address.rsplit(':', 1)
            ipaddress.ip_address(host)
            if not port.isdecimal() or not 1 <= int(port) <= 65535:
                raise ValueError('模拟器 ADB 端口无效')
            self.endpoints.append(DeviceEndpoint(address, transport='tcp', label=label))

    def discover(self):
        return list(self.endpoints)
