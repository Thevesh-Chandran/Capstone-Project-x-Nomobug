# Website feature review — 2 November 2026

## Main tools

| Tool | Value beyond viewing Sheets | Boundary |
| --- | --- | --- |
| Booking calendar | Compares team schedules, travel allowances, normal territory and backup cover; visual day/week slots | Never books automatically. Fresh complete six-team extraction required. |
| Sales and return maps | Proximity groups, density, zoom to source locations, date/size comparisons | Geocoded estimates; no causal pest claims. |
| Customer history | Joins purchases, programme links and visit records across sources | Unresolved identities stay separate. Sheets remains the editing source. |
| Follow-ups | Due-date queue, reminder drafts, saved review/contact progress, source-change checks | Does not mark financial payments or send messages. |
| Dashboard | Aggregate reporting and filters | Reporting belongs here rather than duplicated website pages. |

The main menu now contains Today, Follow-ups, Booking calendar, Sales & return maps, Customer history and Sales dashboard. Payments remains reachable inside Follow-ups rather than another top-level page. District evaluation and forecasts remain available through model evidence; research is collapsed by default. Existing source data and research routes were not deleted.

Today no longer recommends contacting properties based on the unverified location-risk model, offers model-ranked maintenance upsells, or displays speculative marketing/renewal gains. The experimental risk view now states the historical matching and prospective timing limitations. Unconfirmed owner targets no longer receive on-track/behind judgements in the secondary Performance view.

## Verification

- 761 Python tests passed, with 20 existing rasterio deprecation warnings.
- Node calendar DOM and follow-up UI checks passed.
- Authenticated local checks: state, analytics, workspace, booking, spatial, planning, payment follow-up, business totals and reporting all HTTP 200. Evidence: outputs/project_audit/20261102_feature_review/api_checks.json.
- Browser: sign-in, loaded Today, follow-up queue, calendar stale-data rejection, populated maps, hotspot selection and zoom to individual locations, customer history and search reviewed.
- JavaScript syntax checked for edited scripts. Fixed startup ordering so late-loaded navigation attaches to an already-loaded state.

## Open limitations

The local runtime is still the 28 October release. Booking correctly disables availability suggestions while stale; HTTP 200 does not mean it is safe to confirm slots. This needs a successful fresh extraction before operational acceptance. No source freshness timestamps were altered. Online deployment and external dashboard rendering were not verified by this local review. Original frozen predictions, missed windows and model weights are unchanged. Changes in this review are local, not deployed.
