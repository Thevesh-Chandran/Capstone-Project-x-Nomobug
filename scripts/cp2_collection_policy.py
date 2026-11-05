"""Versioned prospective timing, separate from frozen weights and old cohorts."""
from datetime import datetime, time, timedelta, timezone
from hashlib import sha256
import json
from pathlib import Path
from zoneinfo import ZoneInfo

LOCAL = ZoneInfo('Asia/Kuala_Lumpur')
NAME = 'cp2_october10_2026'
TIMING = 'post_end_or_overnight_2345_v1'


def timestamp(value):
    result = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if result.tzinfo is None:
        raise ValueError('Collection timestamp must have a timezone')
    return result.astimezone(timezone.utc)


def record_digest(record):
    return sha256(json.dumps({k:v for k,v in record.items() if k != 'record_sha256'},
        sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def load(root):
    root = Path(root)
    registry = json.loads((root/'config/cp2_model_current.json').read_text())
    expected = registry.get('october10_cohort_protocol_sha256')
    if expected is None:
        return None
    raw = (root/'config/cp2_october10_cohort.json').read_bytes()
    protocol = json.loads(raw)
    start = datetime.fromisoformat(protocol['cohort_start']).date()
    end = datetime.fromisoformat(protocol['cohort_end']).date()
    if (sha256(raw).hexdigest() != expected or protocol.get('record_sha256') != record_digest(protocol)
            or protocol.get('name') != NAME or protocol.get('timing_policy') != TIMING
            or protocol.get('bundle_sha256') != registry['bundle_sha256']
            or protocol.get('target') != 'recorded_corrective_calendar_callback_within_30d'
            or protocol.get('schema_version') != 1 or protocol.get('date_authority') != 'Calendar'
            or not start <= end
            or timestamp(protocol['declared_at_utc']) >= datetime.combine(start, time.min, LOCAL)):
        raise ValueError('Collection protocol integrity or declaration failed')
    return dict(protocol, protocol_sha256=expected)


def active(protocol, start):
    return bool(protocol and protocol['cohort_start'] <= timestamp(start).astimezone(LOCAL).date().isoformat()
                <= protocol['cohort_end'])


def capture_at(start, end, protocol=None):
    start, end = timestamp(start), timestamp(end)
    if start > end:
        raise ValueError('Service scheduling timestamps are reversed')
    day = start.astimezone(LOCAL).date()
    if active(protocol, start) and end.astimezone(LOCAL).date() > day:
        # Planned service details are available before its outcome day. This
        # also covers a late-night appointment scheduled to START after 23:45.
        return datetime.combine(day, time(23, 45), LOCAL).astimezone(timezone.utc)
    return end


def validate_times(start, end, prediction, committed, protocol):
    point = capture_at(start, end, protocol)
    prediction, committed = timestamp(prediction), timestamp(committed)
    if not active(protocol, start) or not point <= prediction <= committed <= point + timedelta(minutes=5):
        raise ValueError('Prediction must be committed within five minutes of the declared capture time')
    if committed.astimezone(LOCAL).date() != timestamp(start).astimezone(LOCAL).date():
        raise ValueError('Prediction must precede the first local callback outcome day')


def sql_capture(start, end):
    return (f"CASE WHEN DATE({end}, 'Asia/Kuala_Lumpur') > DATE({start}, 'Asia/Kuala_Lumpur') "
        f"THEN TIMESTAMP(DATETIME(DATE({start}, 'Asia/Kuala_Lumpur'), TIME '23:45:00'), 'Asia/Kuala_Lumpur') "
        f"ELSE {end} END")
