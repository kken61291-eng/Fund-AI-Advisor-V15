import logging
import smtplib
import os
import time
import functools
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr # [新增] 用于构建标准的邮件地址格式
from datetime import datetime, timedelta
import pytz

# 配置日志格式
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [%(module)s] - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("Xuantie_V15")

def get_beijing_time():
    utc_now = datetime.utcnow()
    beijing_tz = pytz.timezone('Asia/Shanghai')
    return utc_now.replace(tzinfo=pytz.utc).astimezone(beijing_tz)

def retry(retries=3, delay=2):
    """
    函数重试装饰器
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for i in range(retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if i == retries - 1:
                        logger.error(f"❌ {func.__name__} 最终失败: {e}")
                        raise e
                    logger.warning(f"⚠️ {func.__name__} 失败，{delay}秒后重试 ({i+1}/{retries})...")
                    time.sleep(delay)
        return wrapper
    return decorator

def send_email(subject, content):
    sender = os.environ.get('MAIL_USER')
    password = os.environ.get('MAIL_PASS')
    receivers = [sender]

    if not sender or not password:
        logger.warning("未配置邮件账户，跳过发送")
        return

    message = MIMEText(content, 'html', 'utf-8')
    
    # [修复核心] 使用 formataddr 构建符合 RFC 标准的发件人头
    # 格式效果: "玄铁量化 V15 <123456@qq.com>"
    message['From'] = formataddr(("玄铁量化 V15", sender))
    
    message['To'] = Header("Commander", 'utf-8')
    message['Subject'] = Header(subject, 'utf-8')

    try:
        smtp_obj = smtplib.SMTP_SSL('smtp.qq.com', 465)
        smtp_obj.login(sender, password)
        smtp_obj.sendmail(sender, receivers, message.as_string())
        logger.info("📧 邮件发送成功")
    except smtplib.SMTPException as e:
        logger.error(f"邮件发送失败: {e}")
