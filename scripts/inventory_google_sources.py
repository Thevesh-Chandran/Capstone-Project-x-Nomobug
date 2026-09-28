"""Create a metadata-only inventory of approved Google sources.

The script does not download Sheet cell values or Calendar event descriptions.
Its JSON output is local-only and ignored by Git.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SECRET_DIR = PROJECT_ROOT / "secrets"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "profiles" / "google_source_metadata.json"
DEFAULT_TARGET_CALENDARS = {
    "TEAM ACE",
    "TEAM BEAST",
    "SALES TEAM",
    "TEAM DASH",
    "TEAM CHARLIE",
    "REPLACEMENT TECHNICIAN",
}


def configured_path(environment_name: str, default_path: Path) -> Path:
    configured = os.environ.get(environment_name)
    return Path(configured).expanduser() if configured else default_path


def normalize_calendar_name(value: str) -> str:
    """Normalise punctuation and spacing while preserving meaningful words."""
    normalized = re.sub(r"[^A-Z0-9]+", " ", value.upper())
    return " ".join(normalized.split())


def matches_expected_calendar_name(summary: str) -> bool:
    """Allow an expected team name followed by an owner label or suffix."""
    actual = normalize_calendar_name(summary)
    return any(
        actual == target or actual.startswith(f"{target} ")
        for target in DEFAULT_TARGET_CALENDARS
    )


def load_credentials(client_secret_path: Path, token_path: Path) -> Credentials:
    if not client_secret_path.is_file():
        raise SystemExit(
            "OAuth client JSON not found. Place it at "
            f"{client_secret_path} or set NOMOBUG_GOOGLE_CLIENT_SECRET."
        )

    credentials: Credentials | None = None
    if token_path.is_file():
        credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
        if not credentials.has_scopes(SCOPES):
            credentials = None

    if credentials and credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

    if not credentials or not credentials.valid:
        flow = InstalledAppFlow.from_client_secrets_file(
            str(client_secret_path), SCOPES
        )
        credentials = flow.run_local_server(port=8081)
        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding="utf-8")

    return credentials


def load_spreadsheet_ids(source_ids_path: Path) -> list[str]:
    if not source_ids_path.is_file():
        return []

    payload = json.loads(source_ids_path.read_text(encoding="utf-8"))
    spreadsheet_ids = payload.get("spreadsheet_ids", [])
    if not isinstance(spreadsheet_ids, list):
        raise SystemExit("spreadsheet_ids must be a JSON list.")

    cleaned = []
    for spreadsheet_id in spreadsheet_ids:
        value = str(spreadsheet_id).strip()
        if value and value not in cleaned:
            cleaned.append(value)
    return cleaned


def discover_spreadsheets(service: Any, spreadsheet_ids: list[str]) -> list[dict[str, Any]]:
    spreadsheets = []
    fields = (
        "spreadsheetId,properties(title,locale,timeZone),"
        "sheets(properties(sheetId,title,index,sheetType,hidden,"
        "gridProperties(rowCount,columnCount,frozenRowCount,frozenColumnCount)))"
    )
    for spreadsheet_id in spreadsheet_ids:
        metadata = (
            service.spreadsheets()
            .get(spreadsheetId=spreadsheet_id, includeGridData=False, fields=fields)
            .execute()
        )
        spreadsheets.append(metadata)
    return spreadsheets


HEADER_KEYWORDS = {
    "address",
    "amount",
    "campaign",
    "customer",
    "date",
    "email",
    "follow",
    "invoice",
    "lead",
    "name",
    "notes",
    "package",
    "payment",
    "phone",
    "pic",
    "problem",
    "refund",
    "remark",
    "service",
    "source",
    "status",
    "technician",
    "warranty",
}


def looks_like_header(values: list[Any]) -> bool:
    populated = [str(value).strip() for value in values if str(value).strip()]
    if len(populated) < 2:
        return False

    keyword_hits = 0
    for value in populated:
        words = set(normalize_calendar_name(value).lower().split())
        if words.intersection(HEADER_KEYWORDS):
            keyword_hits += 1
    return keyword_hits >= 2


def discover_header_candidates(
    service: Any, spreadsheets: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    candidates = []
    for spreadsheet in spreadsheets:
        spreadsheet_id = spreadsheet["spreadsheetId"]
        for sheet in spreadsheet.get("sheets", []):
            properties = sheet.get("properties", {})
            title = properties.get("title", "")
            grid = properties.get("gridProperties", {})
            candidate_row = int(grid.get("frozenRowCount") or 1)
            escaped_title = title.replace("'", "''")
            response = (
                service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=spreadsheet_id,
                    range=f"'{escaped_title}'!{candidate_row}:{candidate_row}",
                    majorDimension="ROWS",
                )
                .execute()
            )
            values = response.get("values", [[]])
            candidate_values = values[0] if values else []
            high_confidence = looks_like_header(candidate_values)
            candidates.append(
                {
                    "spreadsheet_title": spreadsheet.get("properties", {}).get(
                        "title", ""
                    ),
                    "sheet_title": title,
                    "candidate_row": candidate_row,
                    "status": (
                        "high_confidence_header"
                        if high_confidence
                        else "manual_header_review_required"
                    ),
                    "column_labels": candidate_values if high_confidence else [],
                    "candidate_cell_count": len(candidate_values),
                }
            )
    return candidates


def discover_calendars(service: Any) -> list[dict[str, Any]]:
    calendars = []
    page_token = None
    while True:
        response = (
            service.calendarList()
            .list(maxResults=250, pageToken=page_token, showDeleted=False)
            .execute()
        )
        for item in response.get("items", []):
            summary = item.get("summary", "")
            calendars.append(
                {
                    "id": item.get("id"),
                    "summary": summary,
                    "timeZone": item.get("timeZone"),
                    "accessRole": item.get("accessRole"),
                    "primary": item.get("primary", False),
                    "selected": item.get("selected", False),
                    "target_name_match": matches_expected_calendar_name(summary),
                }
            )
        page_token = response.get("nextPageToken")
        if not page_token:
            break
    return calendars


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory Google Sheets and Calendar metadata without row/event data"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Ignored local JSON output path",
    )
    parser.add_argument(
        "--include-header-candidates",
        action="store_true",
        help="Read one likely header row per tab; does not download full tables",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    client_secret_path = configured_path(
        "NOMOBUG_GOOGLE_CLIENT_SECRET",
        DEFAULT_SECRET_DIR / "google_oauth_client.json",
    )
    token_path = configured_path(
        "NOMOBUG_GOOGLE_TOKEN",
        DEFAULT_SECRET_DIR / "google_token.json",
    )
    source_ids_path = configured_path(
        "NOMOBUG_GOOGLE_SOURCE_IDS",
        DEFAULT_SECRET_DIR / "google_source_ids.json",
    )

    credentials = load_credentials(client_secret_path, token_path)
    spreadsheet_ids = load_spreadsheet_ids(source_ids_path)

    sheets_service = build(
        "sheets", "v4", credentials=credentials, cache_discovery=False
    )
    calendar_service = build(
        "calendar", "v3", credentials=credentials, cache_discovery=False
    )

    spreadsheets = discover_spreadsheets(sheets_service, spreadsheet_ids)
    calendars = discover_calendars(calendar_service)
    header_candidates = (
        discover_header_candidates(sheets_service, spreadsheets)
        if args.include_header_candidates
        else []
    )
    output = {
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "metadata_only": not args.include_header_candidates,
        "cell_access_mode": (
            "one_candidate_header_row_per_tab"
            if args.include_header_candidates
            else "none"
        ),
        "notes": [
            (
                "Only one likely header row per tab was read; full Sheet tables "
                "and Calendar events were not downloaded."
                if args.include_header_candidates
                else "No Sheet cell values or Calendar events were downloaded."
            ),
            "Sheet grid row/column counts are allocated capacity, not used-record counts.",
            "Calendar and spreadsheet IDs in this file must remain local.",
        ],
        "spreadsheets": spreadsheets,
        "calendars": calendars,
        "header_candidates": header_candidates,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2), encoding="utf-8")

    target_count = sum(item["target_name_match"] for item in calendars)
    print(f"Saved metadata-only inventory to {args.output}")
    print(f"Spreadsheets inventoried: {len(spreadsheets)}")
    print(f"Accessible calendars: {len(calendars)}")
    print(f"Expected Calendar name matches: {target_count}")
    if args.include_header_candidates:
        high_confidence_count = sum(
            item["status"] == "high_confidence_header"
            for item in header_candidates
        )
        print(
            "High-confidence header candidates: "
            f"{high_confidence_count}/{len(header_candidates)}"
        )
    if not spreadsheet_ids:
        print(
            "No spreadsheet IDs were configured. Copy the example source-ID file "
            "into secrets/google_source_ids.json and add approved IDs locally."
        )


if __name__ == "__main__":
    main()
