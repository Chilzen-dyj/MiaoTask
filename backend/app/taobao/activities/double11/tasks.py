"""Double 11 task vocabulary injected into the shared pairing algorithm."""
import re
from backend.core.models import Task, TextNode, normalize, bounds_of
from backend.app.common.models.task import TaskRules, parse_tasks as pair_tasks
from backend.app.taobao.utils.task_rules import (ACTION_RE, CLAIM_ACTIONS, DONE_ACTIONS,
    PROGRESS_RE, EXTERNAL_APPS, classify)

RULES = TaskRules(ACTION_RE, PROGRESS_RE,
    re.compile(r'(?:下滑)?浏览\d+[秒sS]|点击去逛|跳转得(?:奖励)?|玩\d+款游戏得|邀请好友成功|去答题最高得|去答题得'),
    frozenset({'累计任务奖励', '当前进度', '音效'}), '累计任务奖励',
    re.compile(r'立即领取|领取奖励|点击领取'), '领取累计任务奖励', classify)

def parse_tasks(nodes, width=1440, height=3200):
    return pair_tasks(nodes, width, height, rules=RULES)

def is_task_list(nodes):
    text = normalize(" ".join(n.text for n in nodes))
    return ("累计任务奖励" in text or
            bool(re.search(r"做任务赚|任务列表|赚能量任务|任务中心", text))) and bool(
                re.search(r"去完成|去浏览|去逛逛|去看看|已完成|已领取|领取奖励|立即领取|明日再来", text))
