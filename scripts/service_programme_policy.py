"""Source-qualified owner-reviewed programme links; never guess customer identity."""
from pathlib import Path
import csv
import hashlib
import re

ROOT = Path(__file__).resolve().parents[1]


def paid_visit_reviews():
    path = ROOT / 'dbt/seeds/paid_programme_visit_overrides.csv'
    rows = list(csv.DictReader(path.read_text(encoding='utf-8').splitlines()))
    if len({r['event_identity_hash'] for r in rows}) != len(rows):
        raise ValueError('Duplicate paid programme event review')
    for row in rows:
        if not re.fullmatch(r'[a-f0-9]{64}', row['event_identity_hash']):
            raise ValueError('Invalid programme event identity')
    return rows


def programme_calendar(raw, classified, reviews=None, *, as_of=None):
    """Independently check reviewed title sequences/dates before reclassification."""
    reviews = paid_visit_reviews() if reviews is None else reviews
    raw_by_hash = {hashlib.sha256(f"{r['calendar_id']}|{r['event_id']}".encode()).hexdigest(): r
                   for r in raw}
    corrections = {}
    from datetime import datetime
    from zoneinfo import ZoneInfo
    for review in reviews:
        if as_of is not None and review['expected_event_date'] > as_of.isoformat():
            continue
        event = raw_by_hash.get(review['event_identity_hash'])
        if event is None:
            raise ValueError('Reviewed paid programme event missing from source')
        day = datetime.fromisoformat(event['start_raw'].replace('Z', '+00:00')).astimezone(
            ZoneInfo('Asia/Kuala_Lumpur')).date().isoformat()
        sequence = re.search(r'\b(\d{1,2})\s*/\s*(\d{1,2})\b', event['summary'] or '')
        if (event['status'] != 'confirmed' or
                re.match(r'^\s*CANCEL(?:L)?ED\b', (event['summary'] or '').upper()) or
                day != review['expected_event_date'] or not sequence or
                tuple(map(int, sequence.groups())) != (int(review['expected_session_current']),
                                                        int(review['expected_session_total']))):
            raise ValueError('Reviewed programme date/sequence/status changed')
        corrections[event['calendar_event_row']] = review
    result = []
    seen = set()
    for row in classified:
        review = corrections.get(row['calendar_event_row'])
        if review:
            if row['warranty_claim_candidate']:
                raise ValueError('Confirmed paid visit conflicts with a warranty label')
            seen.add(row['calendar_event_row'])
            row = dict(row, event_category='service')
        result.append(row)
    if seen != set(corrections):
        raise ValueError('Reviewed paid programme event excluded by source classification')
    return result
