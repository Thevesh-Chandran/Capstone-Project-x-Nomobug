"""Bounded hosted assistant acceptance probe; only aggregate evidence is used.

Run with the existing portal identity in a one-task Cloud Run Job. Generic
answers are retained in restricted project logs; source evidence is omitted.
Automatic checks flag known failure modes, not general reasoning correctness.
"""
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from webapp import assistant, storage

CASES = [
    ('model_comparison', 'How reliable is the model accuracy compared with its baseline?',
     ['94%', '95%', '100 services', '5 recorded']),
    ('rescheduled_3x', 'Can a residential 3x client claim warranty after rescheduling?',
     ['yes', '30 days', 'third']),
    ('area_sales', 'Which district has the highest sales?', ['sales', 'profit']),
    ('commercial_paraphrase', 'A commercial customer bought six visits for ants. Does that include warranty?',
     ['no']),
    ('annual_warranty', 'For a residential 4x package, when does warranty end?', ['30 days']),
    ('green_reminder', 'A payment reminder date cell is green. Does that prove payment was received?',
     ['no']),
    ('unsupported_claims', 'Can we conclude that rainfall caused pest returns and that the area with the highest sales is the most profitable?',
     ['cost', 'caus', 'sales']),
]


def run():
    uri = os.environ['CP2_REVIEW_GCS_URI']
    bucket, prefix = storage.location(uri)
    session = storage.authorized_session()
    obj = '/'.join(filter(None, [prefix, 'business_snapshot.json']))
    response = session.get('https://storage.googleapis.com/storage/v1/b/' + quote(bucket, safe='') +
        '/o/' + quote(obj, safe='') + '?alt=media', timeout=30)
    response.raise_for_status()
    snapshot = response.json()
    registry = json.loads(Path('/app/config/cp2_model_current.json').read_text(encoding='utf-8'))
    results = []
    for case_id, question, expected in CASES:
        started = time.monotonic()
        try:
            result = assistant.ask(question, snapshot, {}, registry)
            answer = (result['answer']+' '+result.get('notice','')).lower()
            missing = [part for part in expected if part.lower() not in answer]
            results.append({'case': case_id, 'question': question, 'result': result,
                'missing_expected_terms': missing, 'latency_seconds': round(time.monotonic()-started, 3),
                'status': 'needs_manual_review' if missing else 'basic_checks_passed'})
        except Exception as error:
            results.append({'case': case_id, 'status': 'failed', 'error_type': type(error).__name__,
                'latency_seconds': round(time.monotonic()-started, 3)})
        print(json.dumps({key: results[-1][key] for key in ('case', 'status', 'latency_seconds')}), flush=True)
    report = {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
        'source_fetched_at_utc': snapshot.get('fetched_at_utc'), 'cases': results,
        'interpretation': 'Scripted acceptance checks; manual answer review required. Not a model accuracy estimate.'}
    # The portal identity is intentionally read-only on its bucket. Keep only
    # generic question/answer text and provider IDs in restricted project logs;
    # omit source evidence rows entirely. The operator saves this to outputs.
    for case in report['cases']:
        if 'result' in case:
            case['result']={k:v for k,v in case['result'].items()
                if k in ('answer','provider','model','sources','notice')}
    print(json.dumps({'assistant_acceptance_report':report}), flush=True)


if __name__ == '__main__':
    run()
