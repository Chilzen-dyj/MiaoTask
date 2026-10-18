"""Bounded, observable task runner for Double 11 and configurable campaigns."""
from collections import Counter
from dataclasses import asdict, dataclass
import json
import hashlib
import logging
from pathlib import Path
import re
import threading
import time

from modules.screen_reader import ScreenReader
from modules.task_model import CLAIM_ACTIONS, TextNode, bounds_of, is_task_list, normalize, parse_tasks

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent


def load_config(path=None):
    import sys
    base = Path(getattr(sys, '_MEIPASS', ROOT))
    config = json.loads((base / 'configs' / 'double11.json').read_text(encoding='utf-8'))
    if path:
        config.update(json.loads(Path(path).read_text(encoding='utf-8')))
    return validate_config(config)


def validate_config(config):
    limits = {
        'default_browse_seconds': (1, 120), 'visit_seconds': (1, 120),
        'browse_extra_seconds': (0, 60),
        'max_task_seconds': (5, 180), 'settle_seconds': (0, 10),
        'page_timeout': (3, 60), 'return_timeout': (5, 90),
        'max_back_steps': (1, 8), 'max_attempts': (1, 3),
        'max_tasks': (1, 300), 'max_scroll_pages': (1, 20),
    }
    for key, (low, high) in limits.items():
        value = config.get(key)
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not low <= value <= high:
            raise ValueError(f'{key} 必须在 {low}～{high} 之间')
        if key.startswith('max_') and key not in ('max_task_seconds',) and not isinstance(value, int):
            raise ValueError(f'{key} 必须是整数')
    for key in ('allow_cross_app', 'ocr', 'scroll_browse', 'claim_rewards'):
        if not isinstance(config.get(key), bool):
            raise ValueError(f'{key} 必须为布尔值')
    if not isinstance(config.get('search_keyword'), str) or len(config['search_keyword']) > 120:
        raise ValueError('活动搜索词过长或格式错误')
    for key in ('entry_labels', 'task_entry_labels'):
        labels = config.get(key)
        if not isinstance(labels, list) or not labels or not all(isinstance(v, str) and 0 < len(v) < 80 for v in labels):
            raise ValueError(f'{key} 必须为非空文字列表')
    return config


class Stopped(Exception):
    pass


class NeedsAttention(Exception):
    pass


class TaskUnavailable(Exception):
    """A terminal condition for this task, rather than a reason to retry it."""
    pass


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


@dataclass
class RunStats:
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    claims: int = 0
    cross_app: int = 0
    attempts: int = 0
    elapsed: int = 0


class CampaignRunner:
    def __init__(self, device, config=None, control=None, emit=None, on_image=None, unavailable_tasks=None):
        self.device = device
        self.config = config or load_config()
        self.control = control or RunControl()
        self.emit = emit or (lambda **event: None)
        self.reader = ScreenReader(device, self.config['ocr'], on_image=on_image)
        self.stats = RunStats()
        self.failures = Counter()
        self.records = {}
        self.origin = None
        self.started = time.monotonic()
        self._external_seen = set()
        self._known_tasks = {}
        self._asset_keys = {}
        self.unavailable_tasks = unavailable_tasks if unavailable_tasks is not None else {}
        self._installed_checked = False
        self._installed_packages = None

    @staticmethod
    def unavailable_key(task):
        return 'app:' + task.target_app if task.target_app else 'task:' + normalize(task.title)

    def availability_reason(self, task, check_installed=False):
        if task.kind in ('manual', 'done', 'claim'):
            return ''
        key = self.unavailable_key(task)
        saved_reason = self.unavailable_tasks.get(key, '')
        if (task.target_packages and self.device.device_type == 'uiautomator2'
                and (check_installed or saved_reason.startswith('未安装'))):
            if not self._installed_checked:
                self._installed_checked = True
                try:
                    packages = self.device.installed_packages()
                    if isinstance(packages, (set, list, tuple)):
                        self._installed_packages = set(packages)
                except Exception:
                    logger.warning('无法读取已安装应用，将依据跳转页面判断', exc_info=True)
            if self._installed_packages is not None:
                if not self._installed_packages.intersection(task.target_packages):
                    reason = f'未安装{task.target_app}，已跳过；安装后重新识别即可恢复'
                    self.unavailable_tasks[key] = reason
                    return reason
                # A new scan refreshes installation state, including after installation.
                if saved_reason.startswith('未安装'):
                    self.unavailable_tasks.pop(key, None)
        return self.unavailable_tasks.get(key, '')

    def check_destination(self, screen):
        if is_task_list(screen.nodes):
            return
        markets = {'com.xiaomi.market', 'com.android.vending', 'com.huawei.appmarket',
                   'com.oppo.market', 'com.heytap.market', 'com.bbk.appstore',
                   'com.tencent.android.qqdownloader'}
        if (screen.package in markets or screen.find(
                r'未安装|尚未安装|没有安装|未找到.{0,8}应用|找不到.{0,8}应用|应用不存在|'
                r'没有可处理|无法.{0,4}(?:打开|跳转)|^(?:立即下载|下载并安装|安装并打开)$')):
            raise TaskUnavailable('目标应用不可用或跳转到安装页，已跳过，不再重复尝试')

    def update(self, phase=None, **data):
        self.stats.elapsed = int(time.monotonic() - self.started)
        self.stats.skipped = sum(r.get('status') in ('manual', 'disabled') for r in self.records.values())
        if phase:
            data['phase'] = phase
        self.emit(stats=asdict(self.stats), **data)

    def read(self, force_ocr=False):
        self.control.check()
        screen = self.reader.read(force_ocr=force_ocr) if force_ocr else self.reader.read()
        self.control.check()
        self.update(package=screen.package, source=screen.source)
        return screen

    def click(self, node):
        self.control.check()
        self.device.click(*node.center)

    def tasks(self, screen):
        cache = getattr(screen, '_campaign_tasks', {})
        if id(self) in cache:
            return cache[id(self)]
        tasks = parse_tasks(screen.nodes, screen.width, screen.height)
        used = set()
        for task in tasks:
            if task.key.startswith('milestone-'):
                continue
            center_y = (task.bounds[1] + task.bounds[3]) / 2
            icons = [n for n in screen.nodes if 'O1CN' in n.text
                     and n.bounds[0] < screen.width * .2
                     and abs(n.center[1] - center_y) < screen.height * .04]
            asset = min(icons, key=lambda n: abs(n.center[1] - center_y)).text if icons else ''
            key = self._asset_keys.get(asset) if asset else None
            old_asset_task = self._known_tasks.get(key)
            if old_asset_task and (old_asset_task.total != task.total or old_asset_task.seconds != task.seconds
                                   or (task.total == 1 and old_asset_task.title != task.title)):
                # A completed one-off offer may be replaced in the same slot,
                # even reusing its icon. It must not inherit the old retry budget.
                key = None
            if key in used:
                key = None
            if key is None:
                # Task captions rotate between product names, search and browse.
                # Match existing repeatable rows by their progress contract and
                # geometry; a newly substituted one-off task gets a fresh ID.
                matches = []
                for old in self._known_tasks.values():
                    if old.key in used or old.total != task.total or old.seconds != task.seconds:
                        continue
                    same_title = old.title == task.title
                    close = abs((old.bounds[1] + old.bounds[3]) / 2 - center_y) < screen.height * .04
                    repeatable = (old.total > 1 and old.seconds > 0
                                  and old.kind in ('browse', 'search', 'done')
                                  and task.kind in ('browse', 'search', 'done'))
                    if same_title or (close and repeatable):
                        matches.append((not close, not same_title, abs(old.current - task.current), old.key))
                if matches:
                    key = min(matches)[-1]
            if key is None:
                key = task.key
                if key in used or key in self._known_tasks:
                    key += '-' + hashlib.sha256((asset or str(task.bounds)).encode()).hexdigest()[:6]
            task.key = key
            used.add(key)
            if asset:
                self._asset_keys[asset] = key
            self._known_tasks[key] = task
        cache[id(self)] = tasks
        screen._campaign_tasks = cache
        return tasks

    def remember(self, tasks):
        for task in tasks:
            previous = self.records.get(task.key, {})
            reason = task.skip_reason or self.availability_reason(task)
            state = ('done' if task.kind == 'done' else 'disabled' if reason.startswith(('已跳过', '未安装', '目标应用'))
                     else 'manual' if task.skip_reason else 'disabled' if reason else 'pending')
            if previous.get('status') in ('failed', 'disabled') and task.current == previous.get('current'):
                if previous['status'] == 'failed' or reason:
                    state = previous['status']
                    reason = reason or previous.get('reason', '')
            self.records[task.key] = dict(task.to_dict(), status=state,
                                          reason=reason)
        self.stats.skipped = sum(r['status'] in ('manual', 'disabled') for r in self.records.values())
        self.update(tasks=list(self.records.values()))

    def guard(self, screen):
        text = normalize(screen.text)
        if re.search(r'滑块|拖动.{0,8}验证|安全验证|请完成验证|验证码|人机验证|操作过于频繁|账号存在风险|访问被拒绝', text):
            raise NeedsAttention('页面要求安全验证，请在手机处理后从当前页面重新开始')
        if re.search(r'短信登录|验证码登录|登录即同意|请先登录|立即登录|授权登录|确认付款|支付密码|确认支付', text):
            raise NeedsAttention('页面要求登录、授权或支付，请在手机处理后从当前页面重新开始')

    def open_task_panel(self, screen):
        if is_task_list(screen.nodes):
            return True
        for label in self.config['task_entry_labels']:
            node = screen.find(label, exact=True)
            if node:
                self.click(node)
                return True
        return False

    def ensure_list(self, auto_open=False):
        self.update('locating', message='识别活动与任务列表')
        screen = self.read()
        self.guard(screen)
        if is_task_list(screen.nodes):
            if not screen.package.startswith('com.taobao.taobao'):
                raise NeedsAttention('当前列表不属于淘宝，请在淘宝打开活动任务列表')
            self.origin = screen.package
            return screen
        panel_clicked = False
        if auto_open:
            package = 'com.taobao.taobao4hmos' if self.device.device_type == 'hmdriver2' else 'com.taobao.taobao'
            if screen.package != package:
                self.device.resume_app(package)
                self.control.wait(1)
                screen = self.read()
            panel_clicked = self.open_task_panel(screen)
            if not panel_clicked:
                # Use actual homepage entries before falling back to search.
                entry = next((screen.find(label, exact=True) for label in self.config['entry_labels']
                              if screen.find(label, exact=True)), None)
                if entry:
                    self.click(entry)
                else:
                    from modules.utils import open_taobao_search
                    open_taobao_search(self.device, self.config['search_keyword'], self.control)
        deadline = self.control.now() + self.config['page_timeout']
        while self.control.now() < deadline:
            self.control.wait(.6)
            screen = self.read()
            self.guard(screen)
            if is_task_list(screen.nodes):
                if not screen.package.startswith('com.taobao.taobao'):
                    raise NeedsAttention('当前列表不属于淘宝，请在淘宝打开活动任务列表')
                self.origin = screen.package
                return screen
            if not panel_clicked and self.open_task_panel(screen):
                panel_clicked = True
        raise NeedsAttention('未识别到任务列表，请在手机打开“领淘金币 → 赚能量”，再选择从当前页面开始')

    def recover(self):
        """Return by observed page state; resume the original task across apps."""
        self.update('returning', message='返回淘宝任务列表')
        deadline = self.control.now() + self.config['return_timeout']
        back_count, resumed, panel_clicked = 0, False, False
        while self.control.now() < deadline:
            screen = self.read()
            if screen.package == self.origin and is_task_list(screen.nodes):
                return screen
            self.guard(screen)
            if screen.package != self.origin:
                if not resumed:
                    logger.info('从 %s 恢复原应用 %s 的活动页面', screen.package, self.origin)
                    self.control.check()
                    self.device.resume_app(self.origin)
                    resumed = True
                    self.control.wait(1)
                    continue
            else:
                if not panel_clicked and self.open_task_panel(screen):
                    panel_clicked = True
                    self.control.wait(.7)
                    continue
                # Give an already-open but temporarily blank panel time to render.
                if re.search(r'做任务赚|累计任务奖励', screen.text) and not self.tasks(screen):
                    self.control.wait(.8)
                    continue
            if back_count >= self.config['max_back_steps']:
                break
            self.control.check()
            self.device.go_back()
            back_count += 1
            self.control.wait(.7)
        raise NeedsAttention('未能恢复原任务列表，已停止返回操作；请在手机进入赚能量列表后重新开始')

    def browse_swipe(self, screen, reverse=False):
        self.control.check()
        start_y, end_y = (.47, .77) if reverse else (.77, .47)
        self.device.swipe(int(screen.width * .5), int(screen.height * start_y),
                          int(screen.width * .5), int(screen.height * end_y), duration=.45)

    @staticmethod
    def search_results_ready(screen):
        if screen.find(r'^历史搜索$|^搜索发现$|^猜你想搜$|^搜索推荐$'):
            return False
        filters = sum(bool(screen.find(pattern)) for pattern in
                      (r'^综合', r'^销量', r'^筛选', r'^店铺', r'^价格'))
        return filters >= 2 and len(screen.nodes) >= 8

    @staticmethod
    def search_controls(tree):
        edits, buttons = [], []
        def walk(item):
            if isinstance(item, list):
                for child in item:
                    walk(child)
            elif isinstance(item, dict):
                attrs = item.get('attributes', item)
                kind = attrs.get('type', attrs.get('class', ''))
                if 'EditText' in kind or 'TextInput' in kind:
                    edits.append(attrs)
                elif (normalize(attrs.get('text') or attrs.get('description') or '') == '搜索'
                      and ('Button' in kind or 'searchbtn' in attrs.get('id', '').lower())):
                    buttons.append(TextNode('搜索', bounds_of(attrs.get('bounds', attrs.get('rect')))))
                for key in ('children', 'hierarchy'):
                    if isinstance(item.get(key), (list, dict)):
                        walk(item[key])
        walk(tree)
        return edits, buttons

    def handle_search(self, screen):
        """Submit a visible query, then require the results page before timing."""
        if self.search_results_ready(screen):
            return True
        edits, buttons = self.search_controls(self.device.dump_hierarchy())
        edit = next((e for e in edits if e.get('focused') in (True, 'true')), edits[0] if edits else None)
        if not buttons:
            buttons = [n for n in screen.nodes if normalize(n.text) == '搜索'
                       and n.center[0] > screen.width * .7 and n.center[1] < screen.height * .22
                       and n.bounds[2] - n.bounds[0] < screen.width * .3]
        if not buttons:
            logger.warning('搜索页没有可确认的提交按钮，不开始浏览计时')
            return False
        button = max(buttons, key=lambda n: n.center[0])
        query = normalize(edit.get('text', '')) if edit else ''
        hint = normalize(edit.get('hint', edit.get('placeholder', ''))) if edit else ''
        if not query or query == hint or query in ('搜索', '搜一搜', '搜索商品'):
            marker = screen.find(r'^搜索发现$|^猜你想搜$|^搜索推荐$')
            candidates = [n for n in screen.nodes if marker
                          and marker.bounds[3] < n.center[1] < marker.bounds[3] + screen.height * .3
                          and 2 <= len(normalize(n.text)) <= 40
                          and not re.search(r'换一换|关闭|隐藏|搜索发现|历史|热搜|登录|https?[:：]|按钮|反馈', n.text)]
            if not edit:
                logger.warning('没有可确认的输入框，不开始浏览计时')
                return False
            query = min(candidates, key=lambda n: (n.center[1], n.center[0])).text if candidates else 'a'
            bounds = bounds_of(edit.get('bounds', edit.get('rect')))
            self.click(TextNode('', bounds))
            self.control.check()
            # Native set_text replaces the field directly, without an IME APK.
            self.device.input_text(query)
            self.control.wait(.3)
        self.click(button)
        logger.info('已点击搜索提交按钮，等待商品结果页')
        deadline = self.control.now() + self.config['page_timeout']
        while self.control.now() < deadline:
            self.control.wait(.5)
            result = self.read()
            self.guard(result)
            if self.search_results_ready(result):
                logger.info('已确认进入搜索结果页，开始浏览计时')
                return True
            if is_task_list(result.nodes):
                return False
        logger.warning('搜索提交后未识别到结果页，结束本次尝试')
        return False

    def execute(self, task, before):
        self.update('opening', current_task=task.title, message='打开任务页面', remaining=0)
        logger.info('执行 %s (%d/%d)，类型 %s', task.title, task.current, task.total, task.kind)
        self.control.check()
        left, top, right, bottom = task.bounds
        self.device.click((left + right) // 2, (top + bottom) // 2)
        self.control.wait(.6)
        deadline = self.control.now() + self.config['page_timeout']
        screen, left = before, False
        searched = False
        while self.control.now() < deadline:
            screen = self.read()
            # Always make the first real jump attempt. Installation evidence is
            # read from this device only, never from a bundled skip list.
            self.check_destination(screen)
            if screen.package == self.origin and is_task_list(screen.nodes):
                after = next((x for x in self.tasks(screen) if x.key == task.key), None)
                if task.kind == 'claim' and after and (after.action != task.action or after.current > task.current):
                    return screen, True, False
                if task.key.startswith('milestone-') and after is None and self.milestone_received(task, screen):
                    return screen, True, False
                self.control.wait(.6)
                continue
            self.guard(screen)
            # Scoped external-app launch confirmation; never accept privacy or login grants.
            if screen.find(r'打开.{0,10}应用|是否.{0,12}打开|即将.{0,10}跳转|允许.{0,12}打开|尝试打开'):
                button = screen.find(r'^(打开|立即打开|继续打开|允许打开|去支付宝|去看看|允许)$')
                if button:
                    if not self.config['allow_cross_app']:
                        break
                    self.click(button)
                    self.control.wait(.8)
                    continue
            if not normalize(screen.text) or len(screen.nodes) < 2:
                self.control.wait(.7)
                continue
            left = True
            break
        if not left:
            logger.warning('任务没有成功离开列表：%s', task.title)
            reason = self.availability_reason(task, check_installed=bool(task.target_packages))
            if reason:
                raise TaskUnavailable(reason)
            return self.recover(), False, False
        cross = screen.package != self.origin
        if cross:
            if not self.config['allow_cross_app']:
                return self.recover(), False, False
            self.stats.cross_app += 1
            logger.info('跨应用浏览：%s', screen.package)
        if task.kind == 'search':
            searched = self.handle_search(screen)
            if not searched:
                return self.recover(), False, cross
            screen = self.read()
        seconds = task.seconds or (self.config['visit_seconds'] if task.kind == 'visit'
                                    else self.config['default_browse_seconds'])
        if task.kind in ('browse', 'search'):
            seconds += self.config['browse_extra_seconds']
        seconds += self.config['settle_seconds']
        browse_started = self.control.now()
        hard_deadline = browse_started + self.config['max_task_seconds']
        browse_deadline = browse_started + min(seconds, self.config['max_task_seconds'])
        remaining = browse_deadline - self.control.now()
        explicit_success = False
        swipe_count = 0
        next_observation = self.control.now() + 3
        while remaining > 0:
            self.control.check()
            self.check_destination(screen)
            self.guard(screen)
            if screen.package == self.origin and is_task_list(screen.nodes):
                break
            if screen.package != self.origin:
                if not cross:
                    self.stats.cross_app += 1
                    cross = True
                if not self.config['allow_cross_app']:
                    break
            if screen.find(r'任务已完成|浏览已完成|浏览完成|完成浏览|奖励已到账|恭喜完成|任务完成啦'):
                explicit_success = True
                logger.info('检测到任务完成提示')
                break
            # Visible remaining countdown may extend, but never exceed the task cap.
            countdown = re.search(r'(?:还需|再逛|再浏览|剩余|再看)[^\d]{0,3}(\d{1,2})\s*秒', screen.text)
            if countdown:
                browse_deadline = max(browse_deadline, min(self.control.now() + int(countdown.group(1)) + 1,
                                                           hard_deadline))
            remaining = browse_deadline - self.control.now()
            self.update('browsing', message='跨应用浏览中' if cross else '浏览中', remaining=max(0, int(remaining + .9)))
            # Sustained scroll gestures keep the activity's browse counter running.
            # Alternate pairs of gestures so finite pages do not stay at the bottom.
            scrolling = self.config['scroll_browse'] and not cross and task.kind in ('browse', 'search')
            if scrolling and remaining > 0:
                self.browse_swipe(screen, reverse=swipe_count % 4 >= 2)
                swipe_count += 1
            interval = max(0, min(.35 if scrolling else 1, browse_deadline - self.control.now()))
            self.control.wait(interval)
            # Pause time must not count as browse time; wait() itself excludes pauses.
            remaining = browse_deadline - self.control.now()
            if remaining > 0 and self.control.now() >= next_observation:
                screen = self.read()
                next_observation = self.control.now() + 3
                remaining = browse_deadline - self.control.now()
        return self.recover(), explicit_success, cross

    @staticmethod
    def list_progress(screen):
        text = normalize(screen.text)
        found = re.search(r'当前进度(\d+)\s*/\s*\d+', text)
        return int(found.group(1)) if found else None

    @staticmethod
    def milestone_received(task, screen):
        header = screen.find('累计任务奖励', exact=True)
        if not header:
            return False
        center_x = (task.bounds[0] + task.bounds[2]) / 2
        return any('已领取' in normalize(n.text)
                   and abs(n.center[0] - center_x) < screen.width * .13
                   and header.bounds[1] - screen.height * .02 < n.center[1] < header.bounds[3] + screen.height * .07
                   and n.bounds[2] - n.bounds[0] < screen.width * .5 for n in screen.nodes)

    def verify(self, task, before, after, explicit=False):
        after_task = next((x for x in self.tasks(after) if x.key == task.key), None)
        if after_task and (after_task.current > task.current or after_task.kind == 'done'
                           or (task.kind != 'claim' and after_task.action in CLAIM_ACTIONS)):
            return True
        if task.kind == 'claim' and after_task and after_task.action != task.action:
            return True
        if task.key.startswith('milestone-'):
            return after_task is None and self.milestone_received(task, after)
        old, new = self.list_progress(before), self.list_progress(after)
        if old is not None and new is not None and new > old:
            return True
        # At the final search repetition Taobao removes the row entirely. The
        # cumulative counter can already be capped at 50/50, so require both
        # visible neighbours and their row-gap contraction instead of assuming
        # that any off-screen/missing row completed.
        if (after_task is None and task.kind in ('browse', 'search', 'visit')
                and task.current == task.total - 1
                and (task.total > 1 or after.source == 'ocr')):
            rows = sorted((t for t in self.tasks(before) if not t.key.startswith('milestone-')),
                          key=lambda t: t.bounds[1])
            index = next((i for i, t in enumerate(rows) if t.key == task.key), -1)
            if 0 < index < len(rows) - 1:
                upper, lower = rows[index - 1], rows[index + 1]
                found = {t.key: t for t in self.tasks(after)}
                if upper.key in found and lower.key in found:
                    upper_after, lower_after = found[upper.key], found[lower.key]
                    gap_before = lower.bounds[1] - upper.bounds[1]
                    gap_after = lower_after.bounds[1] - upper_after.bounds[1]
                    if (abs(upper_after.bounds[1] - upper.bounds[1]) < after.height * .025
                            and 0 < gap_after < gap_before * .75):
                        return True
            elif index == 0 and len(rows) >= 3 and after.source == 'ocr':
                # The first one-off slot also disappears after a successful
                # jump. Require the fixed reward header and TWO following rows
                # moving up together, confirmed from the rendered screenshot.
                header_before = before.find('累计任务奖励', exact=True)
                header_after = after.find('累计任务奖励', exact=True)
                found = {t.key: t for t in self.tasks(after)}
                following = [t for t in rows[1:] if t.key in found][:2]
                if (header_before and header_after
                        and abs(header_before.center[1] - header_after.center[1]) < after.height * .025
                        and len(following) == 2 and following[0].key == rows[1].key):
                    shifts = [t.bounds[1] - found[t.key].bounds[1] for t in following]
                    if (min(shifts) > after.height * .04 and abs(shifts[0] - shifts[1]) < after.height * .025
                            and abs(found[following[0].key].bounds[1] - task.bounds[1]) < after.height * .04):
                        return True
        return explicit and after_task is None

    def scan(self, auto_open=False):
        screen = self.ensure_list(auto_open)
        self.remember(self.tasks(screen))
        self.update('ready', message='已识别当前屏幕任务，可以开始执行')
        return list(self.records.values())

    def run(self, auto_open=False):
        self.started = time.monotonic()
        screen = self.ensure_list(auto_open)
        seen_pages = set()
        scrolls, total_attempts = 0, 0
        while total_attempts < self.config['max_tasks']:
            self.control.check()
            self.guard(screen)
            tasks = self.tasks(screen)
            self.remember(tasks)
            candidates = []
            for task in tasks:
                failure_key = (task.key, task.current)
                if task.kind in ('done', 'manual') or self.records[task.key]['status'] == 'disabled':
                    continue
                if task.kind == 'claim' and not self.config['claim_rewards']:
                    continue
                if not self.config['allow_cross_app'] and task.target_app:
                    self.records[task.key].update(status='disabled', reason='跨应用任务已关闭')
                    continue
                if self.failures[failure_key] < self.config['max_attempts']:
                    candidates.append(task)
            if candidates:
                task = min(candidates, key=lambda t: (self.failures[(t.key, t.current)],
                                                      {'claim': 0, 'browse': 1, 'visit': 2, 'search': 3}.get(t.kind, 4), t.bounds[1]))
                total_attempts += 1
                self.stats.attempts += 1
                self.records[task.key]['status'] = 'running'
                self.update(tasks=list(self.records.values()))
                before = screen
                disabled_reason = ''
                try:
                    after, explicit, cross = self.execute(task, before)
                    success = self.verify(task, before, after, explicit)
                    if not success:
                        # A single short refresh accommodates server-side settlement.
                        self.control.wait(1)
                        # Themis can retain a completed/removed row in its UI
                        # tree. Recheck the rendered page before retrying it.
                        after = self.read(force_ocr=bool(self.config['ocr'] and after.source == 'ui'))
                        if not is_task_list(after.nodes):
                            after = self.recover()
                        success = self.verify(task, before, after, explicit)
                    screen = after
                    if task.kind == 'claim' and success:
                        self.control.wait(.8)
                        screen = self.read()
                        if not is_task_list(screen.nodes):
                            screen = self.recover()
                except TaskUnavailable as exc:
                    disabled_reason = self.availability_reason(task, check_installed=bool(task.target_packages)) or str(exc)
                    self.unavailable_tasks[self.unavailable_key(task)] = disabled_reason
                    screen = self.recover()
                    success = False
                except (Stopped, NeedsAttention):
                    raise
                except Exception:
                    logger.exception('任务执行异常：%s', task.title)
                    screen = self.recover()
                    success = False
                if not success and not disabled_reason and task.target_packages:
                    # Some deeplinks silently stay on a landing page. Only after
                    # that real attempt fails verification do we confirm absence.
                    disabled_reason = self.availability_reason(task, check_installed=True)
                self.remember(self.tasks(screen))
                if disabled_reason:
                    self.records[task.key].update(status='disabled', reason=disabled_reason)
                    logger.info('已跳过 %s：%s', task.title, disabled_reason)
                elif success:
                    if task.kind == 'claim':
                        self.stats.claims += 1
                    else:
                        self.stats.completed += 1
                    updated = next((t for t in self.tasks(screen) if t.key == task.key), None)
                    can_continue = updated and updated.current < updated.total and updated.kind not in ('done', 'claim')
                    self.records[task.key].update(status='pending' if can_continue else 'done',
                                                  reason='已核验本次进度，可继续执行' if can_continue else '已核验任务进度或奖励状态')
                    if updated is None and task.kind == 'claim':
                        self.records[task.key].update(current=task.total, reason='累计任务奖励已领取，已核验奖励状态')
                    elif updated is None and task.current == task.total - 1:
                        self.records[task.key].update(current=task.total, reason='任务完成后已从列表移除，已核验相邻任务位置')
                    logger.info('核验成功：%s', task.title)
                else:
                    self.failures[(task.key, task.current)] += 1
                    exhausted = self.failures[(task.key, task.current)] >= self.config['max_attempts']
                    if exhausted:
                        self.stats.failed += 1
                    self.records[task.key].update(status='failed' if exhausted else 'pending',
                                                  reason='任务进度未增加' + ('，已达尝试上限' if exhausted else '，先执行其他任务'))
                    logger.warning('未核验成功：%s，当前进度 %d，尝试 %d/%d', task.title, task.current,
                                   self.failures[(task.key, task.current)], self.config['max_attempts'])
                self.update(tasks=list(self.records.values()), remaining=0)
                # Progress changed: the same viewport may have newly available tasks.
                seen_pages.clear()
                continue
            signature = tuple((t.key, t.current, t.action) for t in tasks)
            if signature in seen_pages or scrolls >= self.config['max_scroll_pages']:
                break
            seen_pages.add(signature)
            self.update('scanning', message='检查列表下方的任务', current_task='', remaining=0)
            self.control.check()
            self.device.swipe(int(screen.width * .5), int(screen.height * .88),
                              int(screen.width * .5), int(screen.height * .43), duration=.55)
            scrolls += 1
            self.control.wait(.7)
            screen = self.read()
            if not is_task_list(screen.nodes):
                screen = self.recover()
        message = ('达到本轮任务次数上限，可再次开始继续' if total_attempts >= self.config['max_tasks']
                   else '本轮结束，可执行任务已处理；请查看待处理和未通过核验的任务')
        self.update('finished', message=message, current_task='', remaining=0,
                    tasks=list(self.records.values()))
        return asdict(self.stats)
