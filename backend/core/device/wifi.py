"""Explicit Android wireless debugging, using ADB's authenticated TLS pairing.

Discovery reads mDNS advertisements only. It never scans a subnet, pairs an
unselected service, changes USB mode, resets keys or restarts the ADB server.
"""
import ipaddress
import os
import re
import subprocess

from backend.core.device.discovery import (
    AndroidConnectionError, _run_adb, list_android_devices, resolve_adb_binary,
)


def endpoint(value):
    """Accept an explicit IP:port, including bracketed IPv6; never ADB flags."""
    if not isinstance(value, str) or len(value) > 128:
        raise ValueError('请填写手机显示的 IP 地址和端口')
    match = re.fullmatch(r'(\[[0-9a-fA-F:]+\]|[0-9.]+):([0-9]{1,5})', value.strip())
    if not match:
        raise ValueError('地址格式应为 IP:端口，请勿填写网址或省略端口')
    try:
        address = ipaddress.ip_address(match[1].strip('[]'))
    except ValueError:
        raise ValueError('手机 IP 地址无效') from None
    if address.is_unspecified or address.is_multicast or not 1 <= int(match[2]) <= 65535:
        raise ValueError('手机 IP 地址或端口无效')
    host = f'[{address.compressed}]' if address.version == 6 else str(address)
    return f'{host}:{int(match[2])}'


def pairing_code(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{6}', value):
        raise ValueError('配对码应为手机当前显示的六位数字')
    return value


def discover_wifi():
    """Return untrusted advertised endpoints and already-known network devices."""
    binary = resolve_adb_binary()
    services, errors = [], []
    result = _run_adb(binary, ['mdns', 'services'], os.environ.copy(), 8)
    if result.returncode:
        errors.append('无线发现不可用，请手动填写手机显示的地址')
    else:
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) != 3:
                continue
            name, kind, address = fields
            kind = kind.rstrip('.')
            if kind not in ('_adb-tls-pairing._tcp', '_adb-tls-connect._tcp'):
                continue
            try:
                address = endpoint(address)
            except ValueError:
                continue
            item = dict(name=name[:200], kind='pairing' if 'pairing' in kind else 'connect', address=address)
            if item not in services:
                services.append(item)
    devices = [item for item in list_android_devices(binary) if ':' in item['serial']
               or '._adb-tls-connect._tcp' in item['serial']]
    return dict(services=services, devices=devices, errors=errors)


def pair_wifi(address, code, on_status=None):
    """Send the code via stdin, never argv/logs/state/files or raw ADB errors."""
    address, code = endpoint(address), pairing_code(code)
    if on_status:
        on_status('正在配对手机；请保持手机的配对码弹窗打开')
    try:
        result = subprocess.run(
            [resolve_adb_binary(), 'pair', address], input=code + '\n',
            capture_output=True, text=True, encoding='utf-8', errors='replace',
            timeout=20, env=os.environ.copy(),
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0),
        )
    except subprocess.TimeoutExpired:
        raise AndroidConnectionError('配对连接超时；请核对配对端口，并检查校园网是否限制设备互访，可换个人热点重试') from None
    except OSError:
        raise AndroidConnectionError('无法运行无线配对，请检查 ADB 程序是否完整') from None
    finally:
        code = None
    if result.returncode or 'successfully paired' not in result.stdout.lower():
        raise AndroidConnectionError('配对失败；请保持配对弹窗打开，重新填写当前配对地址与配对码。配对端口与连接端口通常不同')
    if on_status:
        on_status('手机已配对；请使用无线调试主页面的连接地址连接')


def connect_wifi(address, on_status=None):
    """One bounded connect attempt; authorization is confirmed by the adapter."""
    address = endpoint(address)
    if on_status:
        on_status('正在连接无线设备；请保持手机解锁并开启无线调试')
    try:
        result = _run_adb(resolve_adb_binary(), ['connect', address], os.environ.copy(), 10)
    except AndroidConnectionError:
        raise AndroidConnectionError('无线连接超时或 ADB 不可用；请核对连接地址，校园网可能限制设备互访') from None
    if result.returncode or not re.search(r'(?:already )?connected to ', result.stdout, re.I):
        raise AndroidConnectionError('无线连接失败；请先配对，核对主页面连接端口。重开无线调试或换网后，地址可能变化')
    return address
