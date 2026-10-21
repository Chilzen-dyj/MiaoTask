"""Bounded task selection, retries and outcome accounting."""
from dataclasses import asdict
import logging
import time
from backend.core.errors import Stopped, NeedsAttention, TaskUnavailable
from backend.core.device.instances import InstanceMismatch
logger = logging.getLogger('backend.execution')

class SessionLoop:
    def run(self, auto_open=False):
        self.started = time.monotonic()
        try:
            screen = self.ensure_list(auto_open)
        except (Stopped, NeedsAttention, InstanceMismatch):
            raise
        except Exception:
            if not auto_open or self._task_restart_used:
                raise
            self.report_failure('初始页面读取异常', phase='locating')
            screen = self.recover(cold_start=True)
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
                if task.kind not in self.config['enabled_task_kinds']:
                    self.records[task.key].update(status='disabled', reason='本轮未选择该任务类型；调整设置后可再次执行')
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
                self._task_restart_used = False
                try:
                    after, explicit, cross = self.execute(task, before)
                    success = self.verify(task, before, after, explicit)
                    if not success:
                        # A single short refresh accommodates server-side settlement.
                        self.control.wait(1)
                        # Themis can retain a completed/removed row in its UI
                        # tree. Recheck the rendered page before retrying it.
                        after = self.read(force_ocr=bool(self.config['ocr'] and after.source == 'ui'))
                        if not self.is_task_list(after.nodes):
                            after = self.recover()
                        success = self.verify(task, before, after, explicit)
                    screen = after
                    if task.kind == 'claim' and success:
                        self.control.wait(.8)
                        screen = self.read()
                        if not self.is_task_list(screen.nodes):
                            screen = self.recover()
                except TaskUnavailable as exc:
                    self.report_failure(str(exc), task, phase='unavailable')
                    disabled_reason = self.availability_reason(task, check_installed=bool(task.target_packages)) or str(exc)
                    self.unavailable_tasks[self.unavailable_key(task)] = disabled_reason
                    screen = self.recover()
                    success = False
                except (Stopped, InstanceMismatch):
                    raise
                except NeedsAttention as exc:
                    if exc.kind != 'navigation' or self._task_restart_used:
                        raise
                    screen = self.recover(cold_start=True)
                    success = self.verify(task, before, screen)
                except Exception:
                    logger.exception('任务执行异常：%s', task.title)
                    self.report_failure('任务执行异常', task)
                    screen = self.recover(cold_start=True)
                    # Reopening may reveal already-settled server progress.
                    success = self.verify(task, before, screen)
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
                    self.report_failure('任务进度未增加', task, phase='verifying')
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
            self._task_restart_used = False
            try:
                self.device.swipe(int(screen.width * .5), int(screen.height * .88),
                                  int(screen.width * .5), int(screen.height * .43), duration=.55)
                scrolls += 1
                self.control.wait(.7)
                screen = self.read()
                if not self.is_task_list(screen.nodes):
                    screen = self.recover()
            except (Stopped, NeedsAttention, InstanceMismatch):
                raise
            except Exception:
                logger.exception('任务列表读取异常')
                self.report_failure('任务列表读取异常', phase='scanning')
                screen = self.recover(cold_start=True)
        message = ('达到本轮任务次数上限，可再次开始继续' if total_attempts >= self.config['max_tasks']
                   else '本轮结束，可执行任务已处理；请查看待处理和未通过核验的任务')
        self.update('finished', message=message, current_task='', remaining=0,
                    tasks=list(self.records.values()))
        return asdict(self.stats)
