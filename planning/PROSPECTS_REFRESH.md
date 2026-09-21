# Manual Prospects refresh

From the activated repository environment, run:

```powershell
python scripts/refresh_prospects_2026.py --refresh
```

The existing NOMOBUG_BQ_UPLOAD_APPROVED=yes setting is still required in your
private .env. The command does not change it or bypass the approval gate.

Sequence: read the live API, validate the 24-column header layout, load or reuse
the content-addressed Bronze table, compare all stored rows/values, pass that
exact snapshot and its original timestamp to dbt, build/test Silver, print the
aggregate checkpoint. Identical content does not create another Bronze table.

Direct dbt builds now require explicit snapshot variables; no stale default is
kept. Use this runner for refreshes. A newer snapshot is not selected by listing
tables or by an arbitrary latest timestamp.

Run only one refresh at a time. This is manual, not scheduled production ETL.
The five-snapshot and 100 MiB payload gates remain. No Neon writes or deletion.
Stop for retention review if the snapshot limit is reached.

Failures stop subsequent steps. A load timeout can leave a committed Bronze
snapshot: rerun verifies and reuses it. A dbt test failure can occur AFTER Silver
has been replaced. Do not treat that as a successful refresh or use it downstream;
there is no atomic publish/automatic rollback in this version. Staged publication
and orchestration locking remain production-hardening work.

Send the final REFRESH PASS line and checkpoint table, or the first failure.
