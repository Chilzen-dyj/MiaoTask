from backend.core.registry import ActivityMeta

META = ActivityMeta('taobao', 'double11', '淘金币双11狂享20亿',
    'backend.app.taobao.activities.double11.activity:Double11Activity',
    default=True, legacy_storage=True)
