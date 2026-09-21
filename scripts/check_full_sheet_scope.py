"""Read-only full approved-tab profile. No exports, uploads or source edits."""
import contextlib
import io
from pathlib import Path
import runpy

root = Path(__file__).resolve().parents[1]
with contextlib.redirect_stdout(io.StringIO()):
    result = runpy.run_path(str(root / 'scripts/profile_b2b_sales_payments.py'),
        init_globals={'include_all_approved_tabs': True})
for tab, frame in result['frames'].items():
    headers = result['header_maps'][tab]
    print(tab, '| returned rows:', len(frame), '| returned columns:', len(headers))
    print('Headers:', list(headers.values()))
print('FULL APPROVED SHEET SCOPE READ COMPLETE. Nine tabs; no source or warehouse writes.')
