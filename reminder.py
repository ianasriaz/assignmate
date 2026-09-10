"""Send email reminders through Purelymail SMTP."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage


def send_reminder(subject: str, body: str) -> None:
    """Send a plain-text reminder using Purelymail credentials from the environment."""
    username = os.environ.get("PURELYMAIL_USER")
    password = os.environ.get("PURELYMAIL_PASS")
    recipient = os.environ.get("PURELYMAIL_TO")
    if not username or not password or not recipient:
        raise RuntimeError(
            "Set PURELYMAIL_USER, PURELYMAIL_PASS, and PURELYMAIL_TO "
            "before sending reminders."
        )

    host = os.environ.get("PURELYMAIL_SMTP_HOST", "smtp.purelymail.com")
    port = int(os.environ.get("PURELYMAIL_SMTP_PORT", "465"))

    message = EmailMessage()
    message["From"] = username
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP_SSL(host, port) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)
