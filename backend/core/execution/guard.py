"""Human verification is a stop condition, never an automatic return action."""
import re
from backend.core.models import normalize
from backend.core.errors import NeedsAttention


def check_attention(session, screen):
    text = normalize(screen.text)
    if re.search(r'滑块|拖动.{0,8}验证|安全验证|请完成验证|验证码|人机验证|操作过于频繁|账号存在风险|访问被拒绝|将满足描述的所有图片拖放到指定区域', text):
        reason = '页面要求安全验证，自动操作已停止；请在手机上本人处理，完成后点击开始自动执行'
        saved = session.report_failure(reason, phase='security')
        raise NeedsAttention(reason, kind='security', evidence_saved=saved)
    if re.search(r'短信登录|验证码登录|登录即同意|请先登录|立即登录|授权登录|确认付款|支付密码|确认支付', text):
        reason = '页面要求登录、授权或支付，请在手机处理后从当前页面重新开始'
        saved = session.report_failure(reason, phase='attention')
        raise NeedsAttention(reason, evidence_saved=saved)
