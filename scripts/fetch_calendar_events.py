import os
import datetime
import argparse
import csv
import re
from html import unescape
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Calendar read-only scope
SCOPES = ['https://www.googleapis.com/auth/calendar.readonly']
TARGET_CALENDARS = {
    'TEAM ACE',
    'TEAM BEAST',
    'SALES TEAM',
    'TEAM DASH',
    'TEAM CHARLIE',
    'REPLACEMENT TECHNICIAN',
}
BASE_DIR = Path(__file__).resolve().parent
CREDS_FILE = BASE_DIR / 'googlesheetscredentials.json'
TOKEN_FILE = BASE_DIR / 'token.json'


def main():
    parser = argparse.ArgumentParser(description='Fetch Calendar events')
    parser.add_argument('--calendar-id', help='Calendar ID to fetch (skip interactive prompt)')
    parser.add_argument('--list-calendars', action='store_true', help='List available calendars and exit')
    parser.add_argument('--calendar-names', nargs='*', help='Fetch only calendars whose summary matches these names')
    parser.add_argument('--max-results', type=int, default=10, help='Number of events to fetch')
    parser.add_argument('--output', help='Output filename (overrides default)')
    args = parser.parse_args()

    creds = None

    # Load saved credentials if available
    if TOKEN_FILE.exists():
        # Read token.json to inspect saved scopes reliably
        import json
        with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
            token_data = json.load(f)
        saved_scopes = set(token_data.get('scopes', []))
        if not set(SCOPES).issubset(saved_scopes):
            print('Existing token.json found but it lacks Calendar scope. Forcing re-auth to add Calendar permission.')
            # back up the old token and force reauth
            os.replace(TOKEN_FILE, BASE_DIR / 'token.json.bak')
            creds = None
        else:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    # If there are no valid credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception:
                creds = None
        if not creds:
            print('Starting OAuth flow on http://localhost:8081/ ...')
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDS_FILE), SCOPES)
            creds = flow.run_local_server(port=8081)

        # Save the credentials for the next run
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('calendar', 'v3', credentials=creds)

        def normalize_name(value):
            return ' '.join(str(value).strip().upper().split())

        def clean_html_text(value):
            if not value:
                return ''
            text = unescape(str(value))
            text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
            text = re.sub(r'</p\s*>', '\n', text, flags=re.I)
            text = re.sub(r'<[^>]+>', '', text)
            text = text.replace('\r', '\n')
            text = re.sub(r'\n{3,}', '\n\n', text)
            return '\n'.join(line.rstrip() for line in text.split('\n')).strip()

        def extract_customer_details(raw_description):
            text = clean_html_text(raw_description)
            if not text:
                return {}

            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if not lines:
                return {}

            data = {
                'customer_name': '',
                'premise_name': '',
                'address': '',
                'package_text': '',
                'problem_text': '',
                'invoice_text': '',
                'email': '',
                'phone_numbers': '',
                'estimated_size': '',
                'raw_description_clean': text,
            }

            key_map = [
                ('customer_name', r'^(?:nama|name)\s*:\s*(.*)$', 1),
                ('premise_name', r'^nama premis\s*:\s*(.*)$', 1),
                ('address', r'^(?:alamat|address)\s*:\s*(.*)$', 1),
                ('package_text', r'^package\s*:\s*(.*)$', 1),
                ('problem_text', r'^problem\s*:\s*(.*)$', 1),
                ('invoice_text', r'^invoice\s*:\s*(.*)$', 1),
                ('email', r'^(?:emel|email)\s*:\s*(.*)$', 1),
                ('phone_numbers', r'^(?:phone no|phone number|phone|no telefon|tel)\s*:\s*(.*)$', 1),
                ('estimated_size', r'^(?:anggaran saiz(?:\s*\(jika tahu\))?)\s*:\s*(.*)$', 1),
            ]

            for line in lines:
                matched = False
                for key, pattern, group_idx in key_map:
                    m = re.match(pattern, line, flags=re.I)
                    if m:
                        data[key] = m.group(group_idx).strip()
                        matched = True
                        break
                if not matched:
                    if re.search(r'premium|commercial|business', line, flags=re.I) and not data['premise_name']:
                        data['premise_name'] = line.strip()

            return data

        def parse_title(summary):
            raw = (summary or '').strip()
            norm = normalize_name(raw)
            session_current = ''
            session_total = ''
            service_stage = 'other'
            event_category = 'other'
            is_consultation = False
            is_warranty_related = False
            is_complimentary_related = False
            is_yearly_subscription = False
            is_one_time = False

            if 'consultation' in norm:
                event_category = 'consultation'
                is_consultation = True
            if 'warranty' in norm or 'claim' in norm or 'callback' in norm:
                is_warranty_related = True
                event_category = 'warranty'
            if 'extra' in norm or 'complimentary' in norm or 'follow-up' in norm or 'follow up' in norm:
                is_complimentary_related = True
                event_category = 'extra'
            if 'yearly' in norm or '12x' in norm or '/12' in norm:
                is_yearly_subscription = True
            if '/1' in norm or '1/1' in norm or 'one time' in norm:
                is_one_time = True

            m = re.search(r'\b(\d{1,2})\s*/\s*(\d{1,2})\b', raw)
            if m:
                session_current = m.group(1)
                session_total = m.group(2)
                if session_current and session_total:
                    if session_current == '1' and session_total == '1':
                        service_stage = 'one_time'
                    elif session_total == '12' or 'yearly' in norm:
                        service_stage = 'yearly_subscription'
                    elif session_current == session_total:
                        service_stage = 'final_session'
                    else:
                        service_stage = 'scheduled_session'
            elif is_consultation:
                service_stage = 'consultation'
            elif is_warranty_related:
                service_stage = 'warranty'
            elif is_complimentary_related:
                service_stage = 'extra'

            return {
                'raw_title': raw,
                'event_category': event_category,
                'session_current': session_current,
                'session_total': session_total,
                'service_stage': service_stage,
                'is_consultation': is_consultation,
                'is_warranty_related': is_warranty_related,
                'is_complimentary_related': is_complimentary_related,
                'is_yearly_subscription': is_yearly_subscription,
                'is_one_time': is_one_time,
            }

        # Let the user choose which calendar to fetch from (or use CLI arg)
        def choose_calendar(svc):
            try:
                resp = svc.calendarList().list().execute()
            except Exception:
                return 'primary'
            items = resp.get('items', [])
            if not items:
                print('No calendars found; using primary.')
                return 'primary'
            print('Available calendars:')
            for i, cal in enumerate(items):
                print(f"{i}: {cal.get('summary')} ({cal.get('id')})")
            sel = input('Select calendar number (or paste calendarId). Press Enter for the first listed: ').strip()
            if sel == '':
                return items[0].get('id')
            # If numeric index
            if sel.isdigit():
                idx = int(sel)
                if 0 <= idx < len(items):
                    return items[idx].get('id')
            # Otherwise assume user pasted an id
            return sel

        def list_target_calendars(svc):
            resp = svc.calendarList().list().execute()
            items = resp.get('items', [])
            wanted = [normalize_name(name) for name in (args.calendar_names or TARGET_CALENDARS)]
            matched = []
            print('Matching calendars:')
            for cal in items:
                summary = cal.get('summary', '')
                cal_id = cal.get('id', '')
                norm_summary = normalize_name(summary)
                if any(target == norm_summary or target in norm_summary for target in wanted):
                    matched.append(cal)
                    print(f"- {summary} ({cal_id})")
            if not matched:
                print('No matching calendars found.')
            return matched

        if args.list_calendars:
            # print then exit
            try:
                resp = service.calendarList().list().execute()
                items = resp.get('items', [])
                for i, cal in enumerate(items):
                    summary = cal.get('summary')
                    cal_id = cal.get('id')
                    norm_summary = normalize_name(summary)
                    marker = ' [TARGET]' if any(target == norm_summary or target in norm_summary for target in TARGET_CALENDARS) else ''
                    print(f"{i}: {summary} ({cal_id}){marker}")
            except Exception as e:
                print(f"Failed to list calendars: {e}")
            return

        # Restrict to today's date (local timezone)
        local_tz = datetime.datetime.now().astimezone().tzinfo
        today = datetime.date.today()
        start_of_day = datetime.datetime.combine(today, datetime.time.min).replace(tzinfo=local_tz)
        end_of_day = datetime.datetime.combine(today, datetime.time.max).replace(tzinfo=local_tz)
        time_min = start_of_day.isoformat()
        time_max = end_of_day.isoformat()

        calendars_to_fetch = []
        if args.calendar_id:
            calendars_to_fetch = [{'summary': args.calendar_id, 'id': args.calendar_id}]
        elif args.calendar_names:
            calendars_to_fetch = list_target_calendars(service)
        else:
            calendars_to_fetch = list_target_calendars(service)
            if not calendars_to_fetch:
                calendar_id = choose_calendar(service)
                calendars_to_fetch = [{'summary': calendar_id, 'id': calendar_id}]

        if not calendars_to_fetch:
            print('No calendars to fetch.')
            return

        all_events = []
        for cal in calendars_to_fetch:
            calendar_id = cal.get('id')
            calendar_name = cal.get('summary', calendar_id)
            print(f'Fetching events for {today.isoformat()} from calendar: {calendar_name} ({calendar_id})...')
            events_result = service.events().list(
                calendarId=calendar_id, timeMin=time_min, timeMax=time_max,
                maxResults=args.max_results, singleEvents=True, orderBy='startTime'
            ).execute()
            events = events_result.get('items', [])
            if not events:
                print('  No events found.')
                continue
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                summary = event.get('summary', 'No Title')
                title_info = parse_title(summary)
                desc_info = extract_customer_details(event.get('description', ''))
                row = {
                    'calendar_name': calendar_name,
                    'calendar_id': calendar_id,
                    'start': start,
                    'end': end,
                    'summary': summary,
                    **title_info,
                    **desc_info,
                }
                all_events.append(row)
                print(f"{calendar_name}\t{start} - {end}\t{summary}")

        if not all_events:
            print('No events found across the selected calendars.')
            return

        if args.output:
            out_path = args.output
        else:
            out_path = 'calendar_events_selected_calendars.csv'

        with open(out_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    'calendar_name', 'calendar_id', 'start', 'end', 'summary',
                    'raw_title', 'event_category', 'session_current', 'session_total',
                    'service_stage', 'is_consultation', 'is_warranty_related',
                    'is_complimentary_related', 'is_yearly_subscription', 'is_one_time',
                    'customer_name', 'premise_name', 'address', 'package_text',
                    'problem_text', 'invoice_text', 'email', 'phone_numbers',
                    'estimated_size', 'raw_description_clean'
                ]
            )
            writer.writeheader()
            writer.writerows(all_events)

        print(f"Saved {len(all_events)} events to {out_path}")

    except HttpError as err:
        print(f'An API error occurred: {err}')


if __name__ == '__main__':
    main()
