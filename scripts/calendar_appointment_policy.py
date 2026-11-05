"""Exact owner-confirmed temporary slots; weekday never determines eligibility.

Reviews bind both Calendar identity and its reviewed start/end. Moving an event
expires its review. This policy does not change cancelled source records, sales,
model weights, or existing immutable prediction/missed-window logs.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re

POLICY_PATH = Path(__file__).resolve().parents[1] / 'dbt/seeds/calendar_appointment_overrides.csv'


def utc(value):
    result = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Appointment review requires timezone-aware timestamps')
    return result.astimezone(timezone.utc)


def load_policy(path=None):
    """Validate the shipped review registry and return parameter-safe rows."""
    rows = list(csv.DictReader((path or POLICY_PATH).read_text(encoding='utf-8').splitlines()))
    identities = set()
    for row in rows:
        identity = row['event_identity_hash']
        if not re.fullmatch(r'[a-f0-9]{64}', identity) or identity in identities:
            raise ValueError('Invalid or duplicate appointment review identity')
        identities.add(identity)
        if (row['appointment_state'] != 'awaiting_client_date' or
                row['reason_code'] != 'owner_confirmed_temporary_slot'):
            raise ValueError('Unsupported appointment review')
        if utc(row['expected_start_at_utc']) > utc(row['expected_end_at_utc']):
            raise ValueError('Appointment review window is reversed')
        utc(row['reviewed_at_utc'])
    return rows


def policy_sha256():
    return hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest()


def is_confirmed_placeholder(event, reviews=None):
    """True only for an exact reviewed identity and unchanged appointment window."""
    identity = hashlib.sha256(
        f"{event.get('calendar_id', '')}|{event.get('event_id', '')}".encode()).hexdigest()
    matching = [row for row in (load_policy() if reviews is None else reviews)
                if row['event_identity_hash'] == identity]
    if not matching:
        return False
    try:
        start, end = utc(event['start_raw']), utc(event['end_raw'])
    except (KeyError, ValueError, TypeError):
        return False
    return any(start == utc(row['expected_start_at_utc']) and
               end == utc(row['expected_end_at_utc']) for row in matching)
