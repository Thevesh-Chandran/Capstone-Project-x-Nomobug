# Website acceptance — 15 October, handover 16 October 2026

Scope: customer lookup, payment follow-up and custom-area exploration. Looker remains with the owner.

## Deployment

Cloud Build `3bd09753-4984-4260-bba8-7e8609299ca5` succeeded, including container import smoke. Cloud Run revision `cp2-portal-00017-fkv` serves 100% of portal traffic. Existing IAP and staff authentication were preserved. No customer data or credentials were included in the staged image source.

Website: https://cp2-portal-964813222593.asia-southeast1.run.app

## Repairs

- Private business endpoints reject mixed reporting releases rather than combine inconsistent totals.
- Date filters reject impossible or reversed dates. The custom-area date controls are visible and Apply also refreshes the radius comparison.
- Missing monetary amounts remain unknown rather than appearing as zero; radius coverage reports unknown sale amounts.
- Duplicate dashboard-style business panels remain hidden; the website retains operational tools.

## Evidence

Full Python suite: **563 passed**, with 19 existing rasterio deprecation warnings. Both frontend JavaScript files passed Node syntax checks.

`outputs/portal_acceptance/20261015/api_acceptance.json` records successful HTTP acceptance against the approved real snapshot, release `cp2r_20261014220032ad32f0`, fetched at 14 October 22:08 UTC (15 October 06:08 Malaysia). Checks cover authentication, linked programmes, empty search, exact payment reconciliation, date-filtered area totals, radius inclusion and invalid dates. This local HTTP check uses the real released data, not fabricated customer fixtures.

There are 39 payment contracts in this release. At the tested centre, 5 km includes 6 purchase rows and 20 km includes 137 across the tested 2026 period. These are business-data counts, not the historical model's 100-service test sample.

Live Chrome verification after deployment confirmed customer search and expansion, including CUST1412 and CUST1569 sharing CONTRACT_0002 while the earlier separate sale remains separate. Payment follow-up loaded all 39 contracts, and the upcoming-seven-days filter reduced the list to seven. The area page displayed its date controls, submitted the 5 km comparison and displayed source-release/coordinate-coverage evidence.

The browser session ended before the final 20 km visual check. On resuming, the new tab required staff sign-in. Therefore the 20 km result is verified by HTTP acceptance, but not claimed as visually verified in the deployed browser. No authentication bypass was attempted.

## Handover

The report draft is `planning/CP2_FINAL_REPORT_DRAFT.md`; the presentation walkthrough is `planning/CP2_DEMO_GUIDE.md`. Both distinguish completed implementation from pending dashboard and prospective results.

The frozen model, its target, thresholds and prediction receipts were not changed by this website release. Future performance is still pending the declared evaluation gates; these application repairs do not establish improved model accuracy. Final report results and dashboard screenshots must be completed after their respective evidence exists.
