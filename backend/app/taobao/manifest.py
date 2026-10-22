from backend.core.registry import AppMeta
from backend.core.device.profile import ApplicationProfile

PROFILE = ApplicationProfile('淘宝', 'com.taobao.taobao', r'com\.taobao\.taobao(?:[._][A-Za-z0-9_]+)*',
    'com.taobao.taobao4hmos', ('com.taobao.taobao@0', 'com.taobao.taobao4hmos@native'))
APP = AppMeta('taobao', '淘宝', PROFILE, default=True)
