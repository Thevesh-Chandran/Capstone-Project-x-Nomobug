# CP2 handover — 16 October 2026

## Open the system

- Website: https://cp2-portal-964813222593.asia-southeast1.run.app
- Maps: sign in first, then open Area explorer → Open hotspot & sales maps, or visit `/maps`.
- Project home: `OPEN_PROJECT.html` in `C:\Users\theve\Desktop\CAPSTONE PROJECT`.
- Staff access code: the private `secrets/portal_token.txt` file. Do not include it in a submission, screenshot, image or repository.

Google access and the staff code remain required. No public access was added to the website. Looker refinement is authorized; the current Google reCAPTCHA connection failure prevents completion. See the consolidated owner review list.

## Implemented and verified

The map workspace is part of the hosted application, rather than just the mockup. It includes sales density, Calendar warranty-signal density, adjustable proximity cells, date filters, pan/zoom, fit-all, keyboard navigation, overlapping-location records and a direct link into customer history. Reset and layer changes clear stale selections.

Density uses mapped records and location uncertainty. Proximity-cell totals exclude uncertain edge matches, so cell totals can be smaller than the mapped-data cards. Sales are recorded package prices, not profit or received cash. Calendar warranty signals do not establish biological recurrence, service completion or formal claim submission.

The model's top cards retain the complete historical evaluation: **100 services, five returns, 94% accuracy versus a 95% no-return baseline**. Only 85 services in that evaluation have usable coordinates. Area results show their own denominators, detected returns, false alerts and misses. Small groups remain grey. The map exposes saved threshold decisions for aggregate reconciliation, not individual risk probabilities. Changing areas does not retrain the model or establish better future accuracy.

Customer drill-through was verified in Chrome: a mapped purchase opens Customers with the sale search populated and returns one matching group. Customer-history programme links, including the owner-confirmed 4 + 20 contract, remain correct.

Payment follow-up loads **39 contracts**. The current release records RM26,461 paid and RM74,545 remaining, rounded for display. These are Sales updates; neither reminder dates nor green cells prove payment receipt or reminder delivery. Unknown values remain unknown.

## Final verification

| Check | Result / evidence |
|---|---|
| Python | 573 passed; 19 existing rasterio deprecation warnings (after assistant response guards) |
| dbt | 155 passed; no warnings, errors or skipped tests |
| Independent source-to-Gold reconciliation | Pass with documented business caveats; no checked row/value mismatches |
| Authenticated real-data API acceptance | Passed against release `cp2r_202610152200214c6271` |
| Frozen-model replay | 5,695 rows reproduced; maximum probability difference below 3.89e-16 |
| Container | Cloud Build import smoke passed |
| Browser | Sales/warranty/model layers, group selection, zoom, marker inspection, customer drill-through and payment totals verified |
| Daily reporting | 16 October 06:08 Malaysia execution succeeded; release audit status PUBLISHED |

Final website build: `cc306b34-5543-4a77-8ab3-7dc312edbb3a`. Revision: `cp2-portal-00022-hd8`, serving 100% of traffic. Prior revision `cp2-portal-00021-9wg` remains the rollback reference. Existing authentication, secret references and service identities were preserved.

Evidence is under `outputs/project_audit/20261016_final/` and `outputs/portal_acceptance/20261016/`. These include private audit material; do not publish the entire directories.

The KPI validator now accepts `--release-manifest`, ensuring that reporting schemas and payment-date sidecars are taken from the same immutable release. The initial stable-schema check and unmatched sidecar check failed; those were invocation/source-selection issues, not accepted results. The final reconciliation used the recorded release and matching sidecar.

The cleanup removed eight compiled SQL files that turned out to be pinned collector inputs. All eight were restored from immutable cloud artifacts and both byte and normalized hashes verified. Future cleanup protects `dbt/target`. Cloud collection and frozen weights were not changed.

## Presentation and submission

Use `CP2_DEMO_GUIDE.md` for the walkthrough, `CP2_FINAL_REPORT_DRAFT.md` for the methods/results draft, and `DASHBOARD_AND_WEBSITE_BUILD_SPEC.md` for the seven dashboard pages and website split. The draft explicitly separates implemented capabilities, exploratory results and pending future evidence.

A strong demonstration shows the checked source pipeline, useful sales/customer geography, linked programme history, payment follow-up and honest model comparisons. Do not describe a high-sales area as profitable without cost data, or claim weather causes returns.

## What cannot be declared complete today

The owner's Looker report and final presentation still need owner review. The report draft needs the final dashboard screenshots and university-specific submission requirements. Cloud Billing was reviewed: 1–15 October project usage RM53.26, offset by RM53.26 other savings, leaving RM0.00 net in the displayed report. Cloud Run accounts for RM48.11 of usage. Billing is delayed and this does not guarantee future free usage; recheck before submission.

The separately predeclared recovery cohort runs **16–30 October**, with governed evaluation scheduled for **30 November at 15:00 Malaysia time**. Complete predictions and outcomes are required. Earlier missed windows remain in their original incomplete cohorts; they were not backfilled. Future results and useful model performance cannot be guaranteed in advance.

The collector and reporting refresh run in cloud services; this laptop need not stay awake. The collector scheduler is restricted to October collection dates. November outcome evaluation is separate. Annual recurring experiment schedules must be retired after the 2026 review, before the next October.

## Latest collection check

At 16 October 11:30 Malaysia time, the collector was responding and the recovery audit recorded zero confirmed missed eligible windows and one unresolved duplicate-paid-session candidate. This is a source-review requirement, not healthy complete coverage. The candidate is being investigated separately; its original missed timestamp remains unchanged. See `outputs/project_audit/20261016_final/operating_summary.json`.

The review found a four-visit sequence in July/October 2025 and January/April 2026, followed by 1/4 in July 2026 and 2/4 in October 2026. The owner has been asked whether the latter is a renewed contract. No contract allocation, eligibility change or late prediction is being inferred while that answer is pending.

## Continued verification and owner review

The assistant now rejects blank or oversized generated answers, unexpected output fields, more than three citations, and invalid evidence references. All 573 Python tests pass. Container build/import smoke passed; real-data API acceptance passed again against the same recorded release. No dbt, frozen model or cohort rules changed in this follow-up.

The far-out map label now retains decimal precision rather than displaying 0.0×. Model mode gives group-selection guidance even when the retained sales view was density. Both were verified on the deployed website. The website README now contains current instructions rather than conflicting historical deployment narratives.

Two live Ollama checks returned correct commercial-no-warranty and residential-4x end-date answers, with evidence; their request latencies were 88.35 and 10.64 seconds. They are limited acceptance examples, not proof of general reasoning reliability.

The latest collector audit at 12:26 pm Malaysia has two unresolved recovery candidates and zero currently confirmed eligible misses. This supersedes the earlier one-candidate snapshot above without erasing it. The consolidated [owner review list](CP2_OWNER_REVIEW.md) records Client M and Hotel client H, the dashboard blocker and future evidence. The owner will check source questions later.

## Website refinement follow-up

The owner has reassigned Looker to themselves. Current website design and workflow verification are recorded in [the website refinement checkpoint](CP2_WEBSITE_REFINEMENT_20261016.md). Python verification now totals 575 passing tests. Hosted refresh failure/recovery was verified using the existing private runtime identity, with no permission expansion; the temporary test job was removed.

Latest website release: `cp2-portal-00025-j2x`, 100% traffic, with six clear tool cards and the stronger heatmap. See the refinement checkpoint for acceptance evidence; this supersedes older revision references above.
