"""Outgoing email over SMTP (plain text). Used for password-reset links.

Tests replace the sender through the get_mail_sender dependency, so no test
ever talks to a real mail server.
"""
import smtplib
import ssl
from email.message import EmailMessage
from typing import Protocol

from app.settings import Settings

SMTP_TIMEOUT_SECONDS = 10


class MailSender(Protocol):
    def send(self, to: str, subject: str, body: str) -> None: ...


class SmtpMailSender:
    def __init__(self, settings: Settings):
        self._settings = settings

    def send(self, to: str, subject: str, body: str) -> None:
        s = self._settings
        msg = EmailMessage()
        msg["From"] = s.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)

        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=SMTP_TIMEOUT_SECONDS) as smtp:
            if s.smtp_starttls:
                smtp.starttls(context=ssl.create_default_context())
            if s.smtp_username:
                smtp.login(s.smtp_username, s.smtp_password or "")
            smtp.send_message(msg)
