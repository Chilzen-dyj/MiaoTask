"""Session state, observation and events."""
from collections import Counter
from dataclasses import asdict
import logging
import time
from backend.core.execution.run_control import RunControl
from backend.core.execution.stats import RunStats
from backend.core.execution.gestures import BrowseGestures
from backend.core.device.instances import AppInstance, InstanceMismatch
from backend.core.device.screen import ScreenReader
logger = logging.getLogger('backend.execution')

class Session:
    def __init__(self, device, config=None, control=None, emit=None, on_image=None, unavailable_tasks=None,
                 on_failure=None):
        self.device = device
        self.config = config or self.default_config()
        self.control = control or RunControl()
        self.emit = emit or (lambda **event: None)
        self.reader = ScreenReader(device, self.config['ocr'], on_image=on_image)
        self.stats = RunStats()
        self.failures = Counter()
        self.records = {}
        target = getattr(device, 'selected_instance', None)
        self.target_instance = target if isinstance(target, AppInstance) else None
        self.origin = self.target_instance.package if self.target_instance else None
        self.gestures = BrowseGestures(self.config)
        self.started = time.monotonic()
        self._external_seen = set()
        self._known_tasks = {}
        self._asset_keys = {}
        self.unavailable_tasks = unavailable_tasks if unavailable_tasks is not None else {}
        self._installed_checked = False
        self._installed_packages = None
        self.on_failure = on_failure
        self._active_task = None
        self._phase = 'locating'
        self._task_restart_used = False


    def report_failure(self, reason, task=None, phase=None):
        """Capture evidence at the failing page, before recovery changes it."""
        if self.on_failure:
            try:
                self.on_failure(reason=reason, task=(task or self._active_task).to_dict()
                                if (task or self._active_task) else None,
                                phase=phase or self._phase)
                return True
            except Exception:
                logger.warning('保存失败现场时发生异常', exc_info=True)
        return False


    def update(self, phase=None, **data):
        self.stats.elapsed = int(time.monotonic() - self.started)
        self.stats.skipped = sum(r.get('status') in ('manual', 'disabled') for r in self.records.values())
        if phase:
            data['phase'] = phase
            self._phase = phase
        self.emit(stats=asdict(self.stats), **data)


    def read(self, force_ocr=False):
        self.control.check()
        screen = self.reader.read(force_ocr=force_ocr) if force_ocr else self.reader.read()
        self.control.check()
        self.assert_instance(screen)
        self.update(package=screen.package, source=screen.source,
                    observation_ms=round(self.reader.last_observation_seconds * 1000))
        return screen


    def assert_instance(self, screen):
        target = self.target_instance
        if target and self.application.matches(screen.package) and (screen.package != target.package or
                target.user_id is not None and screen.user_id != target.user_id):
            raise InstanceMismatch('前台应用与本轮选定实例不一致或无法核定，已停止；不会继续操作另一账号')


    def click(self, node):
        self.control.check()
        self.device.click(*node.center)


    def browse_swipe(self, screen):
        self.control.check()
        x1, y1, x2, y2, duration = self.gestures.sample(screen.width, screen.height)
        self.device.swipe(x1, y1, x2, y2, duration=duration)


    def scan(self, auto_open=False):
        screen = self.ensure_list(auto_open)
        self.remember(self.tasks(screen))
        self.update('ready', message='已识别当前屏幕任务，可以开始执行')
        return list(self.records.values())
