"""从 master 通知适配器精选复用；只使用新版显式配置。"""
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any
from .delivery import DeliveryError, DeliverySuppressed
from .push.wecom import WeComPusher
from .push.serverchan import ServerChanPusher

class LegacyPusherAdapter:
    """复用已有 Server 酱与企业微信实现，同时接入新投递状态机。"""

    def __init__(self, pusher: Any):
        self.pusher = pusher

    def send(self, job: dict) -> None:
        if not self.pusher.available():
            raise DeliverySuppressed("channel_not_configured", "通知渠道尚未配置")
        try:
            self.pusher.send(job["title"], job["content"])
        except Exception as exc:  # requests 与渠道业务错误都由队列统一退避
            raise DeliveryError(
                "channel_request_failed",
                retryable=True,
                outcome_uncertain=True,
                message=str(exc),
            ) from exc


class EmailAdapter:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        username: str,
        password: str,
        sender: str,
    ):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.sender = sender

    def send(self, job: dict) -> None:
        if not self.host or not self.sender or job["destination"] in {"", "configured", "default"}:
            raise DeliverySuppressed("email_not_configured", "邮件通知尚未配置完整")
        message = EmailMessage()
        message["Subject"] = job["title"]
        message["From"] = self.sender
        message["To"] = job["destination"]
        message.set_content(job["content"])
        try:
            with smtplib.SMTP(self.host, self.port, timeout=15) as client:
                client.starttls(context=ssl.create_default_context())
                if self.username:
                    client.login(self.username, self.password)
                client.send_message(message)
        except (OSError, smtplib.SMTPException) as exc:
            raise DeliveryError(
                "smtp_failed",
                retryable=True,
                outcome_uncertain=True,
                message=str(exc),
            ) from exc


def build_adapter(channel, config):
    if channel == 'wecom': return LegacyPusherAdapter(WeComPusher(key=config['key']))
    if channel == 'serverchan': return LegacyPusherAdapter(ServerChanPusher(sendkey=config['sendkey']))
    if channel == 'email': return EmailAdapter(**{k:config[k] for k in ('host','port','username','password','sender')})
    raise DeliverySuppressed('unsupported_channel', '渠道尚未接入')
