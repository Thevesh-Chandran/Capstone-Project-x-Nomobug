# Project clean-up notes, 4 November 2026

These parts were tried and are no longer part of the system. They stay in the repository as evidence; describe each in one line in the report rather than presenting them as features.

| Item | Where | Status | Why |
|---|---|---|---|
| Hand-coded JavaScript business dashboard on Vercel | `frontend/dashboard/`, `/reports` route | No longer linked from the website | Duplicated the Looker report; descriptive charts belong in the dashboard tool |
| Metabase hosted on Vercel | `infra/metabase/` (Vercel files) | Abandoned | Vercel cannot run a Java server of that size (memory and startup failures) |
| Neon database for Metabase | Vercel storage | Unused | Only served the Vercel Metabase trial |
| Metabase on Oracle Always Free | `infra/metabase/oracle/` | Planned | Owner to create the Oracle account; cutoff 12 November, else keep Looker |
| Generative assistant | `webapp/assistant.py` | Removed 1 November | Owner request; endpoints return 410 |
| Warranty risk by property | `#risk` page, `outputs/model_validation/20261102_*` | Research only, removed from the menu | Independent review found map-matching and timing problems |
| Old research scripts | `scripts/research_*`, `scripts/test_*` (not unit tests) | Kept as evidence | 67 older scripts already moved to `archive/` |

## Housekeeping for the owner

- `secrets/` holds seven old `google_token.json.before-renewal-*.bak` files. They are git-ignored, but deleting the old ones reduces risk.
- `tmp/code_snapshot*.tgz` are code copies made for testing on 4 November (git-ignored). Safe to delete.
