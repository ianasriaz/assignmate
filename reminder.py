"""Send email reminders through Purelymail SMTP."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from html import escape


def build_html_email(subject: str, body: str) -> str:
    """Build a readable HTML email with a plain-text-friendly content layout."""
    lines = [line for line in body.splitlines() if line.strip()]
    rendered_lines = []
    for line in lines:
        if " | " in line:
            due, course, title = (part.strip() for part in line.split(" | ", 2))
            rendered_lines.append(
                f'<tr><td class="date">{escape(due)}</td>'
                f'<td><strong>{escape(title)}</strong><br>'
                f'<span class="course">{escape(course)}</span></td></tr>'
            )
        elif ":" in line:
            label, value = line.split(":", 1)
            rendered_lines.append(
                f'<tr><td class="label">{escape(label.strip())}</td>'
                f'<td><strong>{escape(value.strip())}</strong></td></tr>'
            )
        else:
            rendered_lines.append(
                f'<tr><td colspan="2" class="message">{escape(line)}</td></tr>'
            )

    intro = (
        "A deadline is coming up. Here are the details you need to plan your next step."
        if subject.startswith("Deadline ahead")
        else "A quick look at what is coming up in your Classroom."
    )

    return f"""<!doctype html>
<html>
<body style="margin:0;background:#f4f7fb;font-family:Arial,sans-serif;color:#172033;">
  <div style="max-width:620px;margin:24px auto;padding:0 16px;">
    <div style="background:#14213d;border-radius:18px 18px 0 0;padding:28px 32px;color:#fff;">
      <div style="font-size:13px;letter-spacing:1.5px;text-transform:uppercase;color:#9cc9ff;">
        AssignMate
      </div>
      <h1 style="margin:10px 0 0;font-size:25px;line-height:1.25;">{escape(subject)}</h1>
    </div>
    <div style="background:#fff;border:1px solid #e2e8f0;border-top:0;
                border-radius:0 0 18px 18px;padding:28px 32px;">
      <p style="margin:0 0 20px;color:#526071;">{escape(intro)}</p>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="border-collapse:collapse;border:1px solid #e2e8f0;border-radius:10px;">
        {''.join(rendered_lines)}
      </table>
      <div style="margin-top:24px;padding:14px 16px;background:#fff7e6;
                  border-left:4px solid #f59e0b;color:#7c4a03;">
        <strong>Make it easier on yourself:</strong> Put the first small step on
        your schedule now, while the deadline is still ahead.
      </div>
    </div>
    <p style="margin:16px 0;text-align:center;font-size:12px;color:#718096;">
      Sent automatically by AssignMate
    </p>
  </div>
  <style>
    td {{ padding:13px 14px; border-bottom:1px solid #edf2f7; vertical-align:top; }}
    tr:last-child td {{ border-bottom:0; }}
    .date {{ width:34%; color:#2563eb; font-weight:bold; white-space:nowrap; }}
    .label {{ width:34%; color:#64748b; font-weight:bold; }}
    .course {{ color:#64748b; font-size:13px; }}
    .message {{ color:#526071; }}
  </style>
</body>
</html>"""


def send_reminder(subject: str, body: str) -> None:
    """Send a styled HTML reminder with a plain-text fallback."""
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
    message.add_alternative(build_html_email(subject, body), subtype="html")

    with smtplib.SMTP_SSL(host, port) as smtp:
        smtp.login(username, password)
        smtp.send_message(message)


if __name__ == "__main__":
    from google_classroom_assignments import main

    main()
