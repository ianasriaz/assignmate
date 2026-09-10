"""Print upcoming Google Classroom assignments with due dates.

Before running this script:
1. Enable the Google Classroom API in a Google Cloud project.
2. Create an OAuth 2.0 Desktop application and download its client secret as
   ``credentials.json`` in this directory.
3. Install the dependencies from ``requirements.txt``.

The first run opens a browser for Google authorization and stores the
resulting token in ``token.json`` for subsequent runs.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from reminder import send_reminder


SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
]
DEFAULT_CREDENTIALS_FILE = Path("credentials.json")
DEFAULT_TOKEN_FILE = Path("token.json")
DEFAULT_SENT_REMINDERS_FILE = Path("reminders_sent.json")
REMINDER_STAGES = ((timedelta(hours=24), "24-hour"), (timedelta(hours=6), "6-hour"), (timedelta(hours=1), "1-hour"))
PAKISTAN_TIMEZONE = ZoneInfo("Asia/Karachi")


@dataclass(frozen=True)
class Assignment:
    id: str
    due_at: datetime
    course_name: str
    title: str


def authenticate(credentials_file: Path, token_file: Path) -> Credentials:
    """Load cached Google credentials or complete the OAuth flow."""
    credentials: Credentials | None = None

    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if credentials is None or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if os.environ.get("CI") == "true":
                raise RuntimeError(
                    f"Valid Google OAuth token not found at {token_file}; "
                    "headless runs require GOOGLE_TOKEN_JSON."
                )
            if not credentials_file.exists():
                raise FileNotFoundError(
                    f"Google OAuth client secrets not found: {credentials_file}. "
                    "Download credentials.json from Google Cloud Console."
                )
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_file), SCOPES
            )
            # Google may return the equivalent student-submissions scope.
            os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"
            credentials = flow.run_local_server(port=0)

        token_file.write_text(credentials.to_json(), encoding="utf-8")

    return credentials


def list_courses(classroom: Any) -> list[dict[str, Any]]:
    """Return all courses visible to the authenticated user."""
    courses: list[dict[str, Any]] = []
    request = classroom.courses().list(
        courseStates="ACTIVE",
        pageSize=100,
    )

    while request is not None:
        response = request.execute()
        courses.extend(response.get("courses", []))
        request = classroom.courses().list_next(request, response)

    return courses


def list_upcoming_assignments(
    classroom: Any, courses: list[dict[str, Any]]
) -> list[Assignment]:
    """Return assignments with due dates and times that have not passed."""
    now = datetime.now(PAKISTAN_TIMEZONE)
    assignments: list[Assignment] = []

    for course in courses:
        request = classroom.courses().courseWork().list(
            courseId=course["id"],
            courseWorkStates="PUBLISHED",
            pageSize=100,
        )

        while request is not None:
            response = request.execute()
            for coursework in response.get("courseWork", []):
                if coursework.get("workType") != "ASSIGNMENT":
                    continue
                due = coursework.get("dueDate")
                if not due:
                    continue

                due_date = date(
                    due["year"],
                    due["month"],
                    due["day"],
                )
                due_time = coursework.get("dueTime", {})
                due_at = datetime.combine(
                    due_date,
                    time(
                        due_time.get("hours", 23),
                        due_time.get("minutes", 59),
                        due_time.get("seconds", 59),
                    ),
                    tzinfo=PAKISTAN_TIMEZONE,
                )
                if due_at > now:
                    assignments.append(
                        Assignment(
                            coursework["id"],
                            due_at,
                            course.get("name", "Unknown course"),
                            coursework["title"],
                        )
                    )

            request = classroom.courses().courseWork().list_next(request, response)

    return sorted(assignments, key=lambda assignment: (assignment.due_at, assignment.course_name, assignment.title))


def build_three_day_digest(
    assignments: list[Assignment],
) -> str:
    """Build the daily digest for assignments due today through three days from now."""
    today = datetime.now(PAKISTAN_TIMEZONE).date()
    deadline = today + timedelta(days=3)
    due_soon = [assignment for assignment in assignments if assignment.due_at.date() <= deadline]

    if not due_soon:
        return "No assignments are due in the next 3 days."

    return "\n".join(
        f"{assignment.due_at:%Y-%m-%d} | {assignment.course_name} | {assignment.title}"
        for assignment in due_soon
    )


def send_due_reminders(
    assignments: list[Assignment], sent_file: Path
) -> int:
    """Send each reminder stage once when its scheduled time has arrived."""
    now = datetime.now(PAKISTAN_TIMEZONE)
    sent = json.loads(sent_file.read_text(encoding="utf-8")) if sent_file.exists() else {}
    sent_count = 0

    for assignment in assignments:
        for lead_time, stage in REMINDER_STAGES:
            reminder_at = assignment.due_at - lead_time
            key = f"{assignment.id}:{stage}"
            if now >= assignment.due_at or now < reminder_at or key in sent:
                continue

            send_reminder(
                f"{stage} reminder: {assignment.title}",
                (
                    f"Course: {assignment.course_name}\n"
                    f"Assignment: {assignment.title}\n"
                    f"Due: {assignment.due_at:%Y-%m-%d %H:%M PKT}"
                ),
            )
            sent[key] = now.isoformat()
            sent_count += 1

    sent_file.write_text(json.dumps(sent, indent=2), encoding="utf-8")
    return sent_count


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print upcoming Google Classroom assignments."
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        default=DEFAULT_CREDENTIALS_FILE,
        help="Path to the OAuth client secrets JSON file.",
    )
    parser.add_argument(
        "--token",
        type=Path,
        default=DEFAULT_TOKEN_FILE,
        help="Path where the OAuth token should be cached.",
    )
    parser.add_argument(
        "--sent-reminders",
        type=Path,
        default=DEFAULT_SENT_REMINDERS_FILE,
        help="Path where sent reminder stages should be stored.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    credentials = authenticate(args.credentials, args.token)
    classroom = build("classroom", "v1", credentials=credentials)
    assignments = list_upcoming_assignments(classroom, list_courses(classroom))

    if not assignments:
        print("No upcoming assignments.")
    else:
        for assignment in assignments:
            print(
                f"- {assignment.due_at:%Y-%m-%d %H:%M PKT} | "
                f"{assignment.course_name} | {assignment.title}"
            )

    digest = build_three_day_digest(assignments)
    send_reminder("Google Classroom assignments due soon", digest)
    sent_count = send_due_reminders(assignments, args.sent_reminders)
    print(f"Reminder digest sent; {sent_count} staged reminder(s) sent.")


if __name__ == "__main__":
    main()
