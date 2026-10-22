"""Deduplicate authorized transports without accepting prompts or scanning ports."""
from concurrent.futures import ThreadPoolExecutor
import threading
import time

from backend.core.device.discovery import android_identity, list_android_devices, AndroidConnectionError

_lock = threading.RLock()
_cache = {}


def inventory():
    try:
        devices = list_android_devices()
    except AndroidConnectionError as exc:
        return dict(devices=[], errors=[str(exc)])
    def identify(row):
        row = dict(row, type='uiautomator2', status=row['state'])
        if row['state'] != 'device':
            return row, row['serial']
        with _lock:
            cached = _cache.get(row['serial'])
        if cached and time.monotonic()-cached[0] < 15:
            return row, cached[1]
        try:
            identity = android_identity(row['serial'])
        except (OSError,ValueError):
            identity = row['serial']
        with _lock:
            _cache[row['serial']] = time.monotonic(), identity
        return row, identity
    unique = {}
    # Only transports already returned by ADB. No remote address guessing.
    with ThreadPoolExecutor(max_workers=4) as pool:
        for row, identity in pool.map(identify, devices[:32]):
            if identity not in unique:
                unique[identity] = row
    return dict(devices=list(unique.values()), errors=[])
