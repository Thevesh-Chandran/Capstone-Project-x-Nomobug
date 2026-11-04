"""Monthly accuracy check for the return-visit risk model (return_risk_v1).

Input: a matured label export (callback_live_features mature_labels/dataset_input.json), i.e. recent
services with their recorded 30-day outcome. Output: return_risk_monitor.json, shown on the website's
Prediction models page. The frozen model is never refitted; the check only measures it.

  python scripts/monitor_return_risk.py --labels <dataset_input.json> --local <runtime folder>
  python scripts/monitor_return_risk.py --labels <dataset_input.json> --uri gs://<bucket>/<prefix>
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from webapp import return_risk, storage  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--labels', required=True)
    ap.add_argument('--as-of', default=datetime.now(ZoneInfo("Asia/Kuala_Lumpur")).date().isoformat())
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--local')
    g.add_argument('--uri')
    a = ap.parse_args()
    raw = json.loads(Path(a.labels).read_text(encoding='utf-8'))
    rows = [dict(zip(raw['columns'], r)) if isinstance(r, list) else r for r in raw['records']]
    result = return_risk.monitor(rows, date.fromisoformat(a.as_of))
    body = json.dumps(result, indent=1)
    if a.local:
        (Path(a.local) / return_risk.MONITOR).write_text(body, encoding='utf-8')
    else:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / return_risk.MONITOR).write_text(body, encoding='utf-8')
            storage.publish_business(a.uri, tmp, name=return_risk.MONITOR)
    r = result['recent']
    print(f"{result['status']}: last three months {', '.join(r['months'])}, AUC {r['auc']}, "
          f"recorded/expected returns {r['count_factor']}")


if __name__ == '__main__':
    main()
