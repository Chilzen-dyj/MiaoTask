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
    attention_text = text
    passive = getattr(session,'passive_login_banner',None)
    if callable(passive) and passive(screen):
        attention_text = normalize('\n'.join(n.text for n in screen.nodes if normalize(n.text) != '立即登录' or n.center[1] < screen.height*.8))
    if re.search(r'短信登录|验证码登录|登录即同意|请先登录|立即登录|授权登录|欢迎登录|其他方式登录|扫一扫快速登录|确认付款|支付密码|确认支付', attention_text):
        reason = '页面要求登录、授权或支付，请在手机处理后从当前页面重新开始'
        saved = session.report_failure(reason, phase='attention')
        raise NeedsAttention(reason, evidence_saved=saved)
    if getattr(screen,'obscured',False):
        reason='当前应用画面不可读取，可能处于受保护页面；已停止自动输入，请本人检查设备'
        saved=session.report_failure(reason,phase='attention')
        raise NeedsAttention(reason,evidence_saved=saved)
