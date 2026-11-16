"""Source-qualified owner-reviewed programme links; never guess customer identity."""
from collections import defaultdict
from pathlib import Path
import csv
import hashlib
import os
import re

ROOT = Path(__file__).resolve().parents[1]


PAID_VISIT_SEED = 'paid_programme_visit_overrides.csv'


def private_paid_visit_seed():
    configured = os.environ.get('CP2_PRIVATE_PAID_VISIT_SEED')
    if configured:
        path = Path(configured)
        if not path.is_file():
            raise ValueError('Configured private paid-visit seed is unavailable')
        return path
    path = ROOT / 'secrets' / PAID_VISIT_SEED
    return path if path.is_file() else None


def paid_visit_reviews():
    path = private_paid_visit_seed() or ROOT / 'dbt' / 'seeds' / PAID_VISIT_SEED
    rows = list(csv.DictReader(path.read_text(encoding='utf-8').splitlines()))
    if len({r['event_identity_hash'] for r in rows}) != len(rows):
        raise ValueError('Duplicate paid programme event review')
    for row in rows:
        if not re.fullmatch(r'[a-f0-9]{64}', row['event_identity_hash']):
            raise ValueError('Invalid programme event identity')
    return rows


def programme_calendar(raw, classified, reviews=None, *, as_of=None, review_issues=None):
    """Reconcile reviewed visits against the current eligible Calendar records."""
    reviews = paid_visit_reviews() if reviews is None else reviews
    classified_by_row = {row['calendar_event_row']: row for row in classified}
    eligible = defaultdict(list)
    for event in raw:
        row = classified_by_row.get(event['calendar_event_row'])
        if (row is None or row['warranty_claim_candidate'] is not False or
                row['event_date_local'] is None):
            continue
        sequence = re.search(r'\b(\d{1,2})\s*/\s*(\d{1,2})\b', event['summary'] or '')
        if not sequence or event['status'] != 'confirmed' or re.match(
                r'^\s*CANCEL(?:L)?ED\b', event['summary'] or '', re.IGNORECASE):
            continue
        match = (row['sales_record_id'], *map(int, sequence.groups()))
        identity = hashlib.sha256(f"{event['calendar_id']}|{event['event_id']}".encode()).hexdigest()
        eligible['event', identity, *match].append(event['calendar_event_row'])
        if event.get('ical_uid') and event.get('recurring_event_id') is None:
            uid = hashlib.sha256(event['ical_uid'].encode()).hexdigest()
            eligible['ical_uid', uid, *match].append(event['calendar_event_row'])

    corrections = {}
    for review in reviews:
        match = (review['expected_matched_sales_record_id'], int(review['expected_session_current']),
                 int(review['expected_session_total']))
        matches = set(eligible['event', review['event_identity_hash'], *match])
        matches.update(eligible['ical_uid', review.get('ical_uid_hash'), *match])
        if len(matches) == 1:
            row_number = matches.pop()
            if row_number in corrections:
                raise ValueError('One Calendar event assigned to multiple reviewed paid stages')
            corrections[row_number] = review
        elif review_issues is not None and (
                matches or as_of is None or review['expected_event_date'] <= as_of.isoformat()):
            review_issues.append({
                'programme_id': review['programme_id'],
                'paid_programme_stage': int(review['paid_programme_stage']),
                'reason': 'multiple_eligible_matches' if matches else 'no_eligible_historical_match',
            })

    result = []
    for row in classified:
        review = corrections.get(row['calendar_event_row'])
        result.append(dict(row,
            event_category='service' if review else row['event_category'],
            owner_confirmed_paid_stage=review is not None,
            reviewed_programme_id=review['programme_id'] if review else None))
    return result
