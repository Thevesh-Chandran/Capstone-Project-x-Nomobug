# Dashboard and website — agreed split and map specification

16 October 2026. Current interactive map preview: `outputs/dashboard_design/current_spatial_preview/index.html`. The complete-system preview embeds it under Area explorer. These previews do not change the deployed website or Looker.

## Management dashboard: seven useful pages

| Page | Main charts | Supporting detail and filters |
|---|---|---|
| Overview | Monthly sales line; package sales bars; upcoming bookings and source-backed attention list | Sales, purchases, customers and scheduled visits; common date/client/package/pest filters. Sales are package prices, not cash or profit. |
| Sales & customers | Sales over time; customers by new/repeat programme status; highest-sales areas; package mix | Top customers remain private or anonymised. Repeat purchases count separate programmes, so a 1x plus Upsell 2x programme is not two repeat purchases. |
| Enquiries | Recorded enquiry and reply trends; source channels; recorded conversion evidence | Missing follow-up or outcomes stay unknown. Do not infer a sale from a reply. |
| Services & warranty | Booking trend; day/week/month team heatmap; warranty visit signals by package/pest; formal claims separately | Heatmap cells show recorded bookings or scheduled hours. Technician breakdown requires recorded individual assignments. Cancelled visits and parked placeholders are not completed treatments; historical Sundays are not blanket exclusions. |
| Pests & packages | Pest distribution; sales/package comparison; package-by-pest matrix | Keep sales records and visits at separate grains. Do not call a package effective merely because fewer returns are recorded. |
| Areas & weather | Aggregate sales heatmap; aggregate Calendar warranty-signal heatmap; ranked area bars; rainfall/humidity context | Separate sales and return-signal legends. Show geocode coverage and unassigned totals. Weather associations do not establish cause. Custom model subgroup exploration links to the website. |
| Payments | Contract sales/recorded-paid/balance breakdown; upcoming reminders; missing dates; dated refund charts if supported | Use Sales cumulative amounts and source reminder dates. Green cells mean elapsed dates, not paid/sent. Do not infer quarterly amounts or overdue instalments. Missing refund dates must remain visible as excluded coverage, not zero monthly refunds. |

Use stable approved Gold sources rather than dated release datasets. Source candidates are catalogued in `outputs/project_audit/20261016_cleanup/bigquery_catalog.json`; selecting a named source is not a substitute for checking its fields and grain. Old illustrative numbers in the full-system layout are not production acceptance figures.

## Private website: operational tools

| Tool | Interaction | Required evidence |
|---|---|---|
| Customer lookup | Search an authorised customer/sale, open programme history and linked visits | Reviewed identity/programme links. Preserve CUST1412 + CUST1569 as 4 + 20 services; prior 3x remains separate. |
| Payment follow-up | Upcoming reminders, missing dates and positive balances; open the source customer | Approved Sales paid amounts and recorded reminder dates. No outgoing client messages without explicit authorisation. |
| Area explorer | Switch sales / warranty-signal / model layers; heatmap vs proximity cells; pan, zoom and point inspection | Location uncertainty, source period, missing-coordinate coverage and original historical prediction/outcome rows. |
| AI assistant | Explain reviewed figures, warranty policy and model evidence | Verified deterministic calculations for key figures/policy; Ollama for broader supported explanations. No invented profit, causal claims or settlement status. |
| Model & system | Compare forecasts/rankings/return model; inspect test maturity and run evidence | Separate historical evaluation and prospective collection. Keep the original incomplete cohort visible. |

## How the maps should work

1. Start with the business-data layer, not the 100-service model test. Sales uses all eligible source purchases in the chosen period, then reports how many can be mapped. Unique customers and purchases are separate measures.
2. Sales heat intensity is weighted by recorded sales. The warranty map uses recorded Calendar warranty signals. A high count can reflect a high customer volume: it is not automatically a high recurrence rate.
3. Zoom into a group to see geocoded locations. Some locations have area/postcode uncertainty; zooming does not turn these into verified building coordinates. Overlapping records need a list, not one arbitrary record masking the others.
4. Keep private identities and precise points inside authenticated website tools. The current public-link Looker report should use privacy-approved aggregate geography; do not add identifiable customer locations to it.
5. Clicking a model group changes which saved evaluated services are summarised. It does not retrain the model or change a prediction. Show services, positives, accuracy, no-return baseline, detected returns, false alerts and missed returns together.
6. Grey means insufficient evidence. The preview requires at least 20 services and five positives for colour eligibility; this is a display guard, not proof that a subgroup is reliable. All area comparisons remain exploratory. Do not search for the best-looking area and present that result as independent validation.
7. The current preview uses geographic grid cells of adjustable width, not DBSCAN clusters. A production DBSCAN option must state distance, minimum points, noise count and cluster population. Freeze those choices before a fresh comparative evaluation if performance claims will be made.

Looker Studio supports Google Maps heatmap/bubble/fill charts, but its Google Maps charts do not enable ordinary chart drill-down. Pan/zoom is distinct from revealing private customer history or recomputing custom model subgroups. Reference: https://cloud.google.com/looker/docs/studio/google-maps-reference

## Current preview verification and remaining work

The saved release contains 2,502 purchases overall and 1,263 with mapped locations, plus 913 mapped Calendar warranty signals across the source history. Date filters narrow these counts. The model layer uses a distinct 100-service historical evaluation: five positives, two detected, three false alerts and three missed; 94% accuracy versus a 95% no-return baseline.

JavaScript syntax checks passed. Independent calculation checks reproduce these historical model totals. The map supports cells/density display, dates, pan, fit-all, zoom, overlapping-record lists and keyboard map controls. Visual browser acceptance is still pending because the local file URL was blocked by browser security; that rule was not bypassed.

Before production: uncertainty-aware group inclusion, full browser and keyboard acceptance, approved source refresh, authenticated customer links, privacy review of aggregate exports and deployment verification. The current map is a working design prototype; it is not yet part of the hosted website.

## Production update — 16 October

The private hosted `/maps` workspace now implements density/cell layers, uncertainty-aware cell exclusion, pan/zoom, individual mapped-record inspection, overlapping records, district labels, keyboard controls and customer-history drill-through. Live Chrome acceptance passed. The historical top cards retain the full 100-service result, while the map discloses its 85 located services. The original local preview remains a dated design reference; production uses the current approved runtime release.
