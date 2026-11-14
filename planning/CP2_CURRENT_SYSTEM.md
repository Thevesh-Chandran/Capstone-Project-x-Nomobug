# Current system and coverage

Updated 6 November 2026. Deployment revisions and source freshness are runtime facts: check Cloud Run and the website status page instead of treating an old handover as current.

## Hosting and refresh

- Website: https://cp2-portal-fav22krh7q-as.a.run.app/
- Evidence dashboard: the same protected website at `/dashboard/`. Google IAP protects both the website and embedded reporting files.
- Home, the Nomobug logo and Overview open the same management overview. Follow-up counts and staffing figures use the published snapshot. Booking availability uses the team calendars in the booking tool.
- Reporting: Cloud Run `cp2-reporting-daily`, scheduled at 06:00 Malaysia time. Candidate Silver/Gold releases are checked before stable views are published.
- Dashboard: `cp2-dashboard-refresh`, scheduled at 06:45. Build configuration: `dashboard/refresh/cloudbuild.yaml`; run `dashboard/publish.ps1` to refresh with the installed image. Rebuild and update the job image when changing dashboard source.
- Website build: `deploy/cloudbuild.portal-web.yaml` and `deploy/Dockerfile.web`.
- The standalone dashboard service was retired. Vercel and Looker links in dated handovers are legacy entries.

## Business coverage

| Question | Current surface | Meaning and limits |
|---|---|---|
| Sales and customers | Sales & customers | Package sales, customer segments and area comparisons; not profit or cash receipts |
| Prospect conversations | Sales & customers | First-reply records, open/closed annotations and marked-won counts; not unique people or an attributed conversion funnel |
| B2B inspections and conversion | Source validation only | B2B annotations are reconciled; a verified inspection/sale linkage is still needed before publishing a conversion funnel |
| Contract follow-up | Payments and website reminders | Recorded paid totals and balances; dates are reminder dates, not proof an instalment was paid |
| Refunds | Payments | Aggregate recorded refund amounts and review counts; no bank details and no bank-settlement inference |
| Operations | Bookings and staffing; booking calendar | Recorded bookings and capacity estimates; Calendar presence alone does not prove completion |
| Warranty and returns | Return visits and the model | Separate recorded warranty visits and pest returns; no automatic entitlement decision |
| Weather and geography | Maps & patterns | Recorded spatial/weather associations and coverage limits; no causal claims |
| Predictions | Model pages and operational actions | Historical assessment, current estimates and frozen future collection are separate evidence |
| Data quality | Status page and source coverage notes | Freshness, collection gaps and unresolved source facts remain visible |

## Model evidence

The current historical return-ranking assessment does not replace the original frozen 30-day experiment. AUC is ranking discrimination, not classification accuracy. A top-20% comparison is an evaluation benchmark, not a staffing restriction. Follow-up of every customer remains valid.

Missed prospective predictions cannot be repaired retroactively. Final future results require complete outcome windows and the protocol's coverage checks; the November dates are earliest evaluation opportunities, not guaranteed successful results.

## Warehouse navigation

Use `gold` for reporting, `predictions` for published model results, `silver` for cleaned records, `bronze` for immutable source snapshots, `quality` for checks and `audit` for release receipts. `cp2r_*` datasets are release-specific implementations, not separate user dashboards.

Do not rename referenced release datasets or delete them using an old inventory. Current view dependencies, saved rollback definitions, frozen references and configuration must be inventoried first. See [the warehouse catalogue](CP2_WAREHOUSE_RELEASE_CATALOGUE.md). Use `scripts/inventory_reporting_releases.py` to refresh the read-only inventory. An unreferenced release is a review candidate, not automatic permission to erase historical evidence.

## Verification — 6 November fixes

- Python: 776 existing tests passed; two new catalogue/cleanup safety checks passed.
- dbt: 183 checks passed against the published reporting release. The other 31 passed against the shared `analytics_ml` dataset using the same manifest variables with `release_schema_prefix` omitted. Reporting releases build Silver and Gold datasets, while model checks use the shared dataset.
- Independent KPI reconciliation: all 16 checks passed against the latest published release manifest (22 queries, about 11.3 MB processed in total).
- Warehouse catalogue: 54 release datasets; 40 referenced and retained, 14 review-only. No datasets deleted. Private dependency reasons and release manifest are under `outputs/project_audit/20261106_fixes/`.
- Refund records currently have no usable full dates in the aggregate source. They appear as “Date needs checking”; no year is invented and no amount is silently subtracted from sales.
- The historical B2B source annotations reconcile, but no verified prospect-to-sale conversion linkage exists. The gap remains explicit; a funnel would imply facts the sources do not establish.

Dashboard refresh `cp2-dashboard-refresh-6b92t` succeeded on 6 November at 14:49 UTC using build `2b530bfa-050e-4eba-92c7-b34fcfef61a5`. Live Chrome checks confirmed the default range of 1 November 2025–31 October 2026, populated prospect/refund tables and the separate historical/future explanation. The inspected pages logged no browser errors.
