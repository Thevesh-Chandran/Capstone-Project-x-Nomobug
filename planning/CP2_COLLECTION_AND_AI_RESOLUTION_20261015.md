# Collection and assistant resolution — 15 October 2026

The dashboard was not edited. Model weights, thresholds, the 30-day target, original protocols and prediction receipts remain unchanged.

## Candidate investigation

Reviewed all 23 missed candidate windows in the October 10 cohort using the exact frozen transformations and a retained 15 October source snapshot. Every BigQuery query was bounded to 100 MiB. Eight published immutable Calendar snapshots were checked for the two missing event keys.

| Current reconstruction | Windows | Finding |
|---|---:|---|
| Eligible under current frozen predictors | 16 | Two dated 12 October, four dated 13 October, seven dated 14 October, three dated 15 October |
| Package sequence mismatch | 3 | Calendar package/session numbering disagrees with the matched frozen Sales population |
| Duplicate paid session | 2 | Two entries for the same paid session; the frozen model excludes ambiguous anchors |
| Same event rescheduled | 1 | Original 10 October THAS event is now dated 11 October |
| Event absent from current extraction | 1 | Earlier 13 October appointment exists in retained Bronze; current extraction has no matching event identity |

These are current reconstructions, not proof of the exact information available at each original prediction window. No exclusion was used to delete an original miss or manufacture a score. The reason the absent appointment disappeared cannot be inferred from the current extraction. Package/duplicate issues remain frozen-model exclusions unless verified source facts support a separate correction; they are not silently assigned invented dates or package values.

The original audit still contains 60 raw missed candidate windows, including the current cohort's original two classified eligible and 21 unresolved-at-capture candidates. Investigation results are stored separately with source hashes. The original October 10 cohort remains incomplete and cannot yield a strict complete-cohort prospective accuracy result.

The two previously classified eligible misses are dated 12 October. At the first window, cloud logs show a feature-stage ValueError followed by a refresh with no complete prospective logging. At the second, refreshes completed with source exclusions and zero acknowledgements; later source reconstruction now includes that anchor. The retained sanitized logs do not establish the exact first exception message or the original exclusion's business cause, so no more specific root cause is asserted. Later source-stage failures were traced to the deployed image lacking the reviewed B2B column adaptation and repaired in the prior checkpoint.

Private evidence: `outputs/project_audit/20261015_resolution/candidate_review_private.json`, `calendar_key_changes_private.json`, source receipts and query receipts. Nonprivate aggregate summary: `candidate_review_summary.json` in that folder.

## Independent recovery evaluation

Declared at **23:05 Malaysia time on 15 October**, committed as `b1ff8bf`, and stored as an immutable cloud object before collection begins. Protocol: `config/cp2_recovery_cohort.json`; SHA-256 `99d1549ad5910d4c2519888126830251b8d431393024df5cdaa9a7eb50383fff`.

- Service dates: **16–30 October 2026**, every eligible service under the unchanged frozen model population.
- Collection: existing independent cloud collector and original timing protocol. No new model, threshold, selection by outcome or backfilled score.
- Complete outcomes through 29 November; evaluation on **30 November at 15:00 Malaysia time**.
- Dedicated result `prospective_recovery_evaluation.json` and private cloud evidence object. Earlier cohorts and results remain separate.
- Completeness gates reject missing/late receipts, incomplete Calendar outcomes, changed model/protocol/labels, eligibility drift and a second evaluation. Interrupted result uploads recover from the exact durable evidence without recalculating the result.
- Scheduler `cp2-recovery-final-20261130` is enabled. Its cron recurs annually; archive it after the 2026 review. The evaluator itself is one-time and idempotent after finalization.

Recovery does not guarantee future data availability, enough positive cases, or useful accuracy. A strict failure must remain visible if another gap occurs.

## Assistant checks and repairs

Ran a hosted seven-question acceptance review using the portal's existing identity and approved aggregate evidence. Three fixed evidence answers and four broader questions were inspected. Commercial warranty, residential warranty, the historical model/baseline comparison and the sales ranking were consistent with their sources. A compound weather/profit question incorrectly returned only a sales ranking; this was repaired. The green-date answer was correct but incomplete and took about 97 seconds; it now gives the full confirmed meaning directly.

Added deterministic, clearly labelled measurement answers: sales do not establish profit without costs; weather associations do not establish causality; a green reminder date proves neither payment, delivery nor overdue status. Retested area sales, green dates and the compound question in the hosted container: all three passed, with no Ollama call for the two measurement constraints. Broader questions still use Ollama, whose measured response latency remains variable (roughly 10–97 seconds in this small review). This scripted acceptance review is not a general answer-accuracy guarantee.

The first review could not write to the portal bucket because its identity is correctly read-only. No permission was expanded. The rerun retained generic answers and aggregate-only evidence references in restricted project logs, then saved a local review. The temporary review job was deleted.

## Verification

Full Python suite: **557 passed**, 19 existing rasterio warnings. Frozen replay: **5,695 rows**, maximum probability difference below 3.34e-16. Meaningful tests cover missing/late predictions, incomplete outcomes, protocol/model tampering, repeat evaluation, upload recovery, preservation of the old result, current-vs-historical reconciliation and the observed AI failure.

Website build `69b7d037-5c98-49b9-b466-4508d994dd2b`, revision `cp2-portal-00016-6vn`, serves 100% of traffic. Collector base build `85824c22-3442-4781-b8c8-a24d9929df9a` includes the protocol/evaluator; final build `fb4c0beb-3ef1-412d-a717-fb34801fbd3e` layers the tested recovery coverage fields and startup protocol checks onto its immutable digest. The tracked full Dockerfile also reproduces the current source. Collector revision `cp2-prospective-collector-00017-wgg` serves 100%. Startup checks verified the cloud protocol hash before accepting the revision. Final genuine scheduled tick evidence is recorded below when observed.

Genuine scheduled tick at **23:22 Malaysia time** returned HTTP 200 on the new revision. Its durable audit reports recovery status `not_started`, zero recovery candidates/misses, and the unchanged 60 historical raw misses. The two-minute cloud schedule and 30 November recovery evaluation are enabled. The original 14:00 November evaluation remains separate; it must report its original completeness failure rather than use recovery rows as a replacement.
