"""Execution support."""
import threading
import time
from backend.core.errors import Stopped

class RunControl:
    def __init__(self):
        self.stopped = threading.Event()
        self.paused = threading.Event()
        self._paused_seconds = 0.0

    def check(self):
        if self.paused.is_set():
            started = time.monotonic()
            try:
                while self.paused.is_set():
                    if self.stopped.wait(.15):
                        raise Stopped()
            finally:
                self._paused_seconds += time.monotonic() - started
        if self.stopped.is_set():
            raise Stopped()

    def now(self):
        return time.monotonic() - self._paused_seconds

    def wait(self, seconds):
        remaining = max(0, seconds)
        while remaining > 0:
            self.check()
            chunk = min(.15, remaining)
            start = time.monotonic()
            if self.stopped.wait(chunk):
                raise Stopped()
            remaining -= time.monotonic() - start
