# Website acceptance — 18 October 2026

Live Chrome checks resumed after staff sign-in. Payment filters showed 39 contracts in All contracts and four upcoming-seven-day reminders. Payment-to-customer navigation opened CUST2244 and expanded its recorded contract/balance. Sales map totals showed 759 located purchases, 715 customers and RM507,518, with 127 purchases retained as unlocated. Ranking selection, zoom and drill-down to approximate location controls worked. The warranty-visit layer loaded.

The assistant correctly explained green reminder dates and rescheduled residential 3x eligibility using verified evidence. A broader hotspot-marketing-use question timed out after the 45-second Ollama limit. This remains a general generation limitation.

Two concrete repairs were deployed as revision `cp2-portal-00043-mc4`:

- Customer details now show readable programme labels. Linked sales CUST1412 and CUST1569 both displayed Programme 1, with the separate earlier CUST1167 sale displayed as Programme 2. Internal identities are retained behind the presentation.
- Common questions about using the sales map now receive explicit source-backed guidance about source freshness, missing/approximate locations and limits on profit/demand/campaign conclusions. The exact previously timed-out question visibly answered in approximately 250ms after the repair. It is labelled Verified evidence, rather than presented as an Ollama generation.

The full Python suite passed 633 tests with 19 existing rasterio deprecation warnings. Cloud Build `d13b5da1-4557-44c8-860c-9a87505ae4b8` passed its image smoke test. Image digest: `sha256:b11680cb60ad6cda616a90716ea1d6e024631cce75945087b0b6415e96c7ef0b`. The deployed revision serves all traffic. The code-only build context excluded credentials and runtime customer snapshots.

These are focused acceptance examples, not proof that every possible interaction or AI answer is correct. General Ollama latency, three unresolved recovery candidates, missing geography, final spending/reconciliation, dashboard completion and the governed future outcome evaluation remain separately tracked. No frozen prediction model or receipts were altered.

Evidence: `outputs/project_audit/20261018_browser_acceptance/live_browser_results.json` and `assistant_fixed_live.jpg`.
