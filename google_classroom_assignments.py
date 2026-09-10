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
import os
from datetime import date
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/classroom.courses.readonly",
    "https://www.googleapis.com/auth/classroom.coursework.me.readonly",
]
DEFAULT_CREDENTIALS_FILE = Path("credentials.json")
DEFAULT_TOKEN_FILE = Path("token.json")


def authenticate(credentials_file: Path, token_file: Path) -> Credentials:
    """Load cached Google credentials or complete the OAuth flow."""
    credentials: Credentials | None = None

    if token_file.exists():
        credentials = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if credentials is None or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
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
) -> list[tuple[date, str, str]]:
    """Return (due date, course name, assignment title) tuples."""
    today = date.today()
    assignments: list[tuple[date, str, str]] = []

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
                if due_date >= today:
                    assignments.append(
                        (due_date, course.get("name", "Unknown course"), coursework["title"])
                    )

            request = classroom.courses().courseWork().list_next(request, response)

    return sorted(assignments, key=lambda assignment: (assignment[0], assignment[1], assignment[2]))


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
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    credentials = authenticate(args.credentials, args.token)
    classroom = build("classroom", "v1", credentials=credentials)
    assignments = list_upcoming_assignments(classroom, list_courses(classroom))

    if not assignments:
        print("No upcoming assignments.")
        return

    for due_date, course_name, title in assignments:
        print(f"- {due_date.isoformat()} | {course_name} | {title}")


if __name__ == "__main__":
    main()
