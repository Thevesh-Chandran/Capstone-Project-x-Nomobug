> Latest model collection audit (1 November): recovery coverage is incomplete — 24 missed eligible predictions and 16 unresolved candidate windows. Earlier zero-miss statements below describe older checkpoints. A fresh partial assessment of 14 matured, timely receipts found one return, no alerts, 92.9% accuracy equal to the always-no-return baseline, and 0% recall. See [current assessment](CP2_PARTIAL_EVALUATION_20261101.md).

# CP2 — items for owner review

Updated 17 October 2026, Malaysia time. Owner clarification: Client M is the same client; Hotel client H was a free service and therefore has no Sales entry. No source record, frozen model, historical missed-window receipt or cohort protocol has been changed to resolve them.

## 1. Client M — owner confirms normal second service

**18 October owner confirmation:** The July and October 2026 appointments are covered by **CUST1148, dated 29 June 2025**. This resolves the funding-sale question. Preserve the original duplicate-stage/frozen-population decision and missed timestamp; do not create a late prediction or infer a new sale. Repeated stage numbering remains an explicitly documented limitation of the frozen extraction rules, rather than an unanswered owner question.

**Recorded Calendar numbering:** House & Car 4x entries include 1/4 on 17 July 2025, 2/4 on 17 October 2025, 3/4 on 16 January 2026, 4/4 on 16 April 2026, 1/4 on 16 July 2026 and 2/4 on 16 October 2026 (9:45–11:15 am). Numbering alone does not establish a restarted service or a renewed contract.

**Owner confirmed 17 October:** Same client; the October appointment is simply her second service. There is no restarted service. Remove the inferred restart/renewal requirement from the owner questions. Do not invent a new sale, renewal, contract value or additional visit on the basis of numbering.

**Current treatment:** Business interpretation clarified: normal second service. The implementation still needs to reconcile the owner-confirmed stage with the duplicate-session flag and existing source identities. This is an internal linking task, not a request for the owner to confirm a restart. Its original 16 October audit remains preserved; no late prediction was created.

## 2. Hotel client H — resolved business explanation: free service

**Calendar evidence:** “GPC 1/1 Hotel client H”, TEAM CHARLIE, 16 October 2026, 11 am–12 pm.

**Source check:** A fresh read of the approved Sales identity columns and Commercial Clients name column found no “Metro” match. This does not prove the sale is absent: it may use another customer name or spelling. The last published website customer snapshot also had no Metro name match.

**Owner confirmed 17 October:** This was a free service, which is why no sale was recorded. Do not request or fabricate a paid Sales match. Retain it as a free booking/service in operational reporting, distinct from paid package sales and warranty claims.

**Current treatment:** Owner explanation recorded. The original noon audit remains preserved. Any retrospective cohort reclassification must be separately documented against the exact event identity and protocol; this clarification is not evidence that a prediction was logged on time. Runtime classification has not been silently changed by this documentation update.

## Project items separate from source review

- **Dashboard:** Google reports that its reCAPTCHA service cannot connect. Scorecards and payment tables were visible earlier, but chart panels were blank. The monthly sales/packages chart was configured with separate axes; visual verification and remaining page refinements are incomplete. No security setting was weakened.
- **Future model result:** Recovery services run 16–30 October; complete 30-day outcomes are evaluated on 30 November, subject to the existing completeness checks. This is pending evidence, not a repair that can be completed today. Earlier missed windows remain visible.
- **AI quality:** Two additional live Ollama warranty answers were correct. Request latencies were approximately 88 and 11 seconds. This is a small acceptance check, not a general accuracy claim.

## Latest collection status

**18 October internal source investigation:** DC3's 16 October appointment is matched to CUST2032, but the current Sales snapshot contains CUST2485 dated 11 October with matching customer name/address and one session. That newer row has a blank phone field, explaining why the phone-based match fell back to the older sale. A source-supported correction candidate is identified; no owner guess is required. Applying a new match to the frozen cohort would require a separately documented eligibility/drift decision and cannot supply a missed timely prediction. Private evidence is in `outputs/project_audit/20261018_completion/`.

**17 October 23:31 MYT update:** The cloud collector is current. Its recovery audit now has three unresolved candidates and zero confirmed eligible misses: Client M and Metro (owner explanations already recorded above), plus Learning-centre client with a duplicate-paid-session flag. The first two require internal implementation reconciliation, not repeated owner clarification. DC3 needs an internal contract/sequence evidence check before asking for any missing business fact. All original missed timestamps remain preserved.

The 16 October 12:26 pm audit reports 62 historical raw missed candidate windows, including two unresolved candidates in the recovery cohort and zero currently confirmed missed eligible windows. The status is **requires_source_review**. Zero confirmed eligible misses does not establish complete coverage while candidates remain unresolved.

Private evidence is in `outputs/project_audit/20261016_final/`. Do not publish that entire folder; it contains customer-linked source material.
