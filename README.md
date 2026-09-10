# AssignMate

AssignMate fetches upcoming Google Classroom assignments and sends polished
email reminders through Purelymail. All due dates and reminder calculations use
Pakistan Standard Time (PKT, `Asia/Karachi`).

## Local setup

1. Enable the Google Classroom API in Google Cloud Console.
2. Create an OAuth 2.0 Desktop client and save the downloaded file as
   `credentials.json` in the repository directory.
3. Install dependencies:

   ```powershell
   python -m pip install -r requirements.txt
   ```

4. Run the script:

   ```powershell
   python google_classroom_assignments.py
   ```

The first local run opens a browser for Google authorization and creates
`token.json`. Both files are ignored by Git and must never be committed.

Set these environment variables before sending email locally:

```powershell
$env:PURELYMAIL_USER="your-purelymail-address"
$env:PURELYMAIL_PASS="your-purelymail-password"
$env:PURELYMAIL_TO="recipient@example.com"
python reminder.py
```

## GitHub Actions

The workflow in `.github/workflows/reminder.yml` runs daily at 03:00 UTC,
which is 08:00 PKT, and can also be started manually from the Actions tab.

Create these repository Actions secrets:

| Secret | Value |
| --- | --- |
| `PURELYMAIL_USER` | Purelymail SMTP username |
| `PURELYMAIL_PASS` | Purelymail SMTP password |
| `PURELYMAIL_TO` | Reminder recipient address |
| `GOOGLE_CREDENTIALS_JSON` | Base64-encoded `credentials.json` |
| `GOOGLE_TOKEN_JSON` | Base64-encoded authorized `token.json` |

Encode the Google files on Windows without placing their contents in the
repository:

```powershell
$encoded = [Convert]::ToBase64String([IO.File]::ReadAllBytes(".\credentials.json"))
$encoded | Set-Clipboard
```

Paste that value into `GOOGLE_CREDENTIALS_JSON`. Repeat with `token.json` for
`GOOGLE_TOKEN_JSON`. The workflow decodes both secrets at runtime and never
stores them in the repository.

## Reminder behavior

For every future assignment with a due date, AssignMate can send reminders:

- 24 hours before the due time
- 6 hours before the due time
- 1 hour before the due time

Each message includes the course, assignment, and due time in PKT. Classroom
API times are interpreted as UTC and converted to `Asia/Karachi`; for example,
Classroom's `18:59` UTC appears as `23:59 PKT`. Coursework without an explicit
time uses 23:59:59 PKT. Sent stages are tracked in the local, ignored
`reminders_sent.json` file. Assignments that are already past due are skipped.

## Security

Never commit `credentials.json`, `token.json`, `reminders_sent.json`, `.env`
files, or SMTP passwords. If a credential is exposed, revoke or rotate it
immediately in Google Cloud Console or Purelymail. GitHub Actions secrets are
masked and are only available to workflows in the repository.
