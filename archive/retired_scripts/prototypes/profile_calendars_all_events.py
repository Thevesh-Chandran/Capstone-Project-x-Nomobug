"""Load and profile all historical events from six Nomobug calendars.

Run locally:
    python scripts/prototypes/profile_calendars_all_events.py

The default window is 2000-01-01 through today. Pagination retrieves every
event occurrence in that finite period. Raw output remains Git-ignored.
"""

import datetime as dt
import json
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


START_DATE = dt.date(2000, 1, 1)
END_DATE = dt.date.today()
TIMEZONE = "Asia/Kuala_Lumpur"

project_root = Path(__file__).resolve().parents[2]
token_path = project_root / "secrets" / "google_token.json"
metadata_path = project_root / "data" / "profiles" / "google_source_metadata.json"
raw_directory = project_root / "data" / "raw" / "calendar"
profile_directory = project_root / "data" / "profiles" / "calendar"

raw_directory.mkdir(parents=True, exist_ok=True)
profile_directory.mkdir(parents=True, exist_ok=True)

scopes = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
]

credentials = Credentials.from_authorized_user_file(str(token_path), scopes)
calendar_service = build(
    "calendar", "v3", credentials=credentials, cache_discovery=False
)

metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
target_calendars = [
    calendar
    for calendar in metadata.get("calendars", [])
    if calendar.get("target_name_match")
]

if len(target_calendars) != 6:
    raise SystemExit(
        f"Expected six confirmed Nomobug calendars, found {len(target_calendars)}."
    )

local_timezone = ZoneInfo(TIMEZONE)
time_min = dt.datetime.combine(
    START_DATE,
    dt.time.min,
    tzinfo=local_timezone,
).isoformat()
time_max = dt.datetime.combine(
    END_DATE + dt.timedelta(days=1),
    dt.time.min,
    tzinfo=local_timezone,
).isoformat()

all_event_rows = []
calendar_summary_rows = []

for calendar in target_calendars:
    calendar_name = calendar.get("summary", "")
    calendar_id = calendar.get("id", "")
    page_token = None
    calendar_event_rows = []

    while True:
        response = (
            calendar_service.events()
            .list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                timeZone=TIMEZONE,
                maxResults=2500,
                singleEvents=True,
                orderBy="startTime",
                showDeleted=False,
                pageToken=page_token,
            )
            .execute()
        )

        for event in response.get("items", []):
            start = event.get("start", {})
            end = event.get("end", {})

            event_row = {
                "calendar_name": calendar_name,
                "calendar_id": calendar_id,
                "event_id": event.get("id"),
                "ical_uid": event.get("iCalUID"),
                "status": event.get("status"),
                "event_type": event.get("eventType"),
                "start": start.get("dateTime") or start.get("date"),
                "end": end.get("dateTime") or end.get("date"),
                "is_all_day": bool(start.get("date") and not start.get("dateTime")),
                "summary": event.get("summary"),
                "description": event.get("description"),
                "location": event.get("location"),
                "created": event.get("created"),
                "updated": event.get("updated"),
                "recurring_event_id": event.get("recurringEventId"),
            }
            calendar_event_rows.append(event_row)
            all_event_rows.append(event_row)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    calendar_df = pd.DataFrame(calendar_event_rows)
    parsed_starts = pd.to_datetime(
        calendar_df.get("start", pd.Series(dtype="string")),
        errors="coerce",
        utc=True,
    )

    calendar_summary_rows.append(
        {
            "calendar_name": calendar_name,
            "event_rows": len(calendar_df),
            "distinct_event_ids": (
                calendar_df["event_id"].nunique(dropna=True)
                if "event_id" in calendar_df
                else 0
            ),
            "earliest_start_utc": parsed_starts.min(),
            "latest_start_utc": parsed_starts.max(),
            "all_day_events": (
                int(calendar_df["is_all_day"].sum())
                if "is_all_day" in calendar_df
                else 0
            ),
            "missing_summary": (
                int(calendar_df["summary"].isna().sum())
                if "summary" in calendar_df
                else 0
            ),
            "missing_description": (
                int(calendar_df["description"].isna().sum())
                if "description" in calendar_df
                else 0
            ),
        }
    )

    print(f"{calendar_name}: events={len(calendar_df):,}")

events_df = pd.DataFrame(all_event_rows)
raw_path = raw_directory / "nomobug_calendar_events_all_history.csv"
events_df.to_csv(raw_path, index=False)

if len(events_df):
    column_profile = pd.DataFrame(
        {
            "column": events_df.columns,
            "non_null_count": events_df.notna().sum().to_numpy(),
            "missing_count": events_df.isna().sum().to_numpy(),
            "missing_percent": (
                events_df.isna().mean() * 100
            ).round(2).to_numpy(),
            "distinct_count": events_df.nunique(dropna=True).to_numpy(),
        }
    )
else:
    column_profile = pd.DataFrame(
        columns=[
            "column",
            "non_null_count",
            "missing_count",
            "missing_percent",
            "distinct_count",
        ]
    )

profile_path = profile_directory / "calendar_column_profile.csv"
column_profile.to_csv(profile_path, index=False)

calendar_summary = pd.DataFrame(calendar_summary_rows)
summary_path = profile_directory / "calendar_summary.csv"
calendar_summary.to_csv(summary_path, index=False)

print("\nDate window:", START_DATE, "through", END_DATE)
print("Total event rows:", f"{len(events_df):,}")
print("Exact duplicate rows:", f"{int(events_df.duplicated().sum()):,}")
print("Saved raw events:", raw_path)
print("Saved profile:", profile_path)
print("Saved Calendar summary:", summary_path)
