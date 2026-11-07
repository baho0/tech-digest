"""SMTP delivery. Works with Gmail (App Password) or any self-hosted server:
only the TD_SMTP_* / TD_MAIL_* settings change."""

from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from ..render.renderer import Rendered
from ..settings import Settings


class SmtpNotifier:
    def __init__(self, settings: Settings) -> None:
        if not settings.mail_to:
            raise ValueError("TD_MAIL_TO is empty")
        if not (settings.mail_from or settings.smtp_user):
            raise ValueError("Set TD_MAIL_FROM or TD_SMTP_USER")
        self.s = settings

    def build(self, message: Rendered) -> EmailMessage:
        msg = EmailMessage()
        sender = self.s.mail_from or self.s.smtp_user
        msg["Subject"] = message.subject
        msg["From"] = sender
        msg["To"] = ", ".join(self.s.mail_to)
        msg["Date"] = formatdate(localtime=True)
        domain = (sender or "").rsplit("@", 1)[-1].strip(" >") or None
        msg["Message-ID"] = make_msgid(domain=domain)
        msg.set_content(message.text)
        msg.add_alternative(message.html, subtype="html")
        return msg

    def send(self, message: Rendered) -> None:
        s = self.s
        msg = self.build(message)
        ctx = ssl.create_default_context()
        if s.smtp_security == "ssl":
            server: smtplib.SMTP = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout, context=ctx)
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout)
        with server:
            server.ehlo()
            if s.smtp_security == "starttls":
                server.starttls(context=ctx)
                server.ehlo()
            if s.smtp_user and s.smtp_password:
                server.login(s.smtp_user, s.smtp_password)
            server.send_message(msg)


def build_notifier(settings: Settings) -> SmtpNotifier:
    return SmtpNotifier(settings)
