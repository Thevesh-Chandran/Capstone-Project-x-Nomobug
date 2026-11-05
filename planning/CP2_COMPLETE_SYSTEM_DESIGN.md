# Complete system design — proposal, 14 October 2026

This is a mockup proposal, not a live dashboard or website deployment. Existing sources and public/private access remain unchanged. The dashboard is embedded inside the website; operational tools do not recreate its aggregate reporting.

## Looker dashboard: seven management pages

| Page | Content retained from earlier pages |
|---|---|
| Overview | Main sales/booking/warranty figures, trend, area comparison, aggregate attention items |
| Sales & customers | Sales trends, purchase counts, customer mix, repeat programmes and repeat-customer sales; all-history customer scope explicit |
| Enquiries | Enquiry trends, staff statuses, source breakdown, payment-link context; no unsupported conversion or cash claims |
| Services & warranty | Bookings, team breakdown, Calendar warranty signals, formal claims separately, return intervals; cancellations/reschedules excluded appropriately |
| Pests & packages | Package and pest sales/bookings, missing categories, comparisons at their own grains |
| Areas & weather | District comparisons, unknown location coverage, prior rainfall/humidity comparisons, weather denominators and observational limitation |
| Payments | Aggregate arrangement sales/recorded paid/remaining balance, staff reminder schedule and missing-date coverage; Sales only |

Source freshness belongs in a compact report-level footer/information control. Exact source dates, coverage and definitions remain inspectable. Refund records belong in a Services & warranty detail only if dated, validated rows support it; absence of dated rows is not a zero-refund claim. DBSCAN radius scenarios belong in the website's area explorer with supporting aggregate output where available.

## Private website: tools and supporting evidence

| Section | Purpose |
|---|---|
| Dashboard | Embed the seven Looker reporting pages; avoid duplicating their charts as website pages |
| Customers | Authorised customer search, programme/purchase/visit history, reviewed upsell links and identity uncertainty |
| Payment follow-up | Client-level reminder list, balances from Sales, missing-date/source review; no inferred overdue instalment, sent status or automated messages |
| Area explorer | District/radius interactions, valid spatial coverage and source-backed details; historical model subgroup evidence separate from business population |
| AI assistant | Ollama explanations using approved evidence, citations and deterministic verified key figures; no autonomous client messaging or guaranteed reasoning correctness |
| Model & system | Historical results, threshold/top-20 metrics and baseline; comparisons; future protocol/coverage; missing windows; detailed source checks and refresh/failure history |

## Scope and verification

The mockup includes six website sections, seven dashboard views, four model/system views and three prewritten AI example answers. Navigation and example selection passed a minimal JavaScript DOM-stub smoke check. This is not browser visual acceptance. Charts/queues explicitly marked illustrative are not production results. No private client details, fresh source queries or live model calls are included.

Previous pages are consolidated, not deleted from production. The user must be able to inspect this proposal before live implementation. Keep the separate all-history customer scope, separate payment/claim/booking grains, frozen model and existing permissions intact.
