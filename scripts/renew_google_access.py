"""Renew local read-only Google consent without downloading source records.

Run only when sign-in renewal is required: python scripts/renew_google_access.py
Uses localhost:8081/, confirmed by the student in Google Console.
Does not change the client. Windows refused local port 8080.
"""

import json
import os
import tempfile
import uuid
from pathlib import Path

from dotenv import load_dotenv
from google_auth_oauthlib.flow import InstalledAppFlow

project_folder = Path(__file__).resolve().parents[1]
load_dotenv(project_folder / ".env")
client_path = Path(os.getenv("NOMOBUG_GOOGLE_CLIENT_SECRET") or "secrets/google_oauth_client.json").expanduser()
token_path = Path(os.getenv("NOMOBUG_GOOGLE_TOKEN") or "secrets/google_token.json").expanduser()
if not client_path.is_absolute():
    client_path = project_folder / client_path
if not token_path.is_absolute():
    token_path = project_folder / token_path

# Refuse an unexpected storage destination; existing private credentials stay in secrets.
secret_folder = (project_folder / "secrets").resolve()
if not token_path.parent.is_dir() or token_path.is_symlink():
    raise SystemExit("Token folder is missing or the token is a link. Review local configuration first.")
token_path = token_path.resolve()
if token_path.parent != secret_folder:
    raise SystemExit("This renewal script expects the token directly inside the project's ignored secrets folder.")
try:
    config = json.loads(client_path.read_text(encoding="utf-8-sig"))
except (ValueError, OSError):
    raise SystemExit("Cannot read the existing OAuth client. Do not paste its contents into chat.") from None
# The downloaded JSON may predate Console edits. Google validates the callback
# against the current server-side registration, not this exported redirect list.

scopes = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]
print("Opening Google sign-in. Choose the account with access to Nomobug's sources.")
print("Only read-only Sheets and Calendar permissions are requested. No source records will be read.")
try:
    flow = InstalledAppFlow.from_client_config(config, scopes)
    credentials = flow.run_local_server(
        host="localhost", port=8081, timeout_seconds=180,
        prompt="consent", access_type="offline",
        authorization_prompt_message="Complete Google consent in the browser; do not share the callback URL.",
        success_message="Sign-in completed. You can close this tab and return to your terminal.",
    )
except Exception as error:
    raise SystemExit(f"Sign-in did not complete ({type(error).__name__}). Existing token unchanged.") from None
if not credentials.valid or not credentials.refresh_token or not credentials.has_scopes(scopes):
    raise SystemExit("Required read-only consent/refresh token is missing. Existing token unchanged.")

# Save only after successful consent. Keep a unique private backup of the old token.
new_token = credentials.to_json()
if token_path.is_file():
    backup_path = token_path.with_name(token_path.name + ".before-renewal-" + uuid.uuid4().hex + ".bak")
    with backup_path.open("xb") as backup:
        backup.write(token_path.read_bytes())
with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=secret_folder, suffix=".tmp", delete=False) as pending:
    pending.write(new_token)
    pending_path = Path(pending.name)
os.replace(pending_path, token_path)
print("Google sign-in renewed. Token saved privately; previous token backed up if present.")
print("Next: python scripts/extract_prospects_2026.py")
