"""External destination availability and installation evidence."""
import logging
from backend.core.errors import TaskUnavailable
logger = logging.getLogger('backend.execution')

class DestinationPolicy:
    def check_destination(self, screen):
        if self.is_task_list(screen.nodes):
            return
        markets = {'com.xiaomi.market', 'com.android.vending', 'com.huawei.appmarket',
                   'com.oppo.market', 'com.heytap.market', 'com.bbk.appstore',
                   'com.tencent.android.qqdownloader'}
        if (screen.package in markets or screen.find(
                r'未安装|尚未安装|没有安装|未找到.{0,8}应用|找不到.{0,8}应用|应用不存在|'
                r'没有可处理|无法.{0,4}(?:打开|跳转)|^(?:立即下载|下载并安装|安装并打开)$')):
            raise TaskUnavailable('目标应用不可用或跳转到安装页，已跳过，不再重复尝试')


    def unavailable_landing(self, screen):
        try:
            self.check_destination(screen)
        except TaskUnavailable as exc:
            return str(exc)
        return ''


    def remember_missing_destination(self, screen):
        """Without an active task, only persist an identified, absent app fact."""
        if self.device.device_type != 'uiautomator2':
            return
        try:
            packages = self.device.installed_packages()
        except Exception:
            return
        if not isinstance(packages, (set, list, tuple)):
            return
        for name, targets in self.external_apps:
            if name in screen.text and not set(packages).intersection(targets):
                reason = f'未安装{name}，已跳过；安装后重新识别即可恢复'
                self.unavailable_tasks['app:' + name] = reason
                logger.info(reason)
