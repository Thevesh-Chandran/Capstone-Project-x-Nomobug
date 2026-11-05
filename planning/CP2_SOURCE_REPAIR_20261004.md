# Source formula repair — 4 October 2026

Source formulas were repaired directly in the two existing Google Sheets workbooks, after live metadata and CellData inspection. This is a completed source edit, not a local preview. New reporting snapshots must still be refreshed to pick up these source corrections.

## Completed changes

| Workbook / cells | Repair | Verification |
| --- | --- | --- |
| SESSION & PAYMENT, SALES `AG2346:AG2347` | Restored remaining-balance arithmetic to each sale's own `AB - AC - AE`; removed a deleted reference and previous-row deposit reference. | Both currently calculate 0.00; input amounts unchanged. |
| SESSION & PAYMENT, SALES `F5:F2477` | Duration is calculated only when both closed and lead dates are numeric; missing or placeholder dates remain blank. | All 2,473 formula texts read back exactly; Commercial Clients and Recurring Payments inherited duration errors are now absent. |
| SESSION & PAYMENT, existing SALES helpers `AH5:AN2233` | Preserved 5/1/31/36/50 day offsets. Missing `-`, NA, N/A, PENDING or blank base dates no longer create errors or fake 1899/1900 reminder dates. Restored 11 deleted references and 18 references into another sale's row. | All 15,411 existing formulas read back exactly. 12,668 unaffected valid numeric helper results remained identical. Fourteen downstream changes follow directly from corrected cross-row base references. |
| SESSION & PAYMENT, 23 PAYMENTS name lookup cells | Lookups now use their own row's already-existing, unique SALES ID. No payment IDs, amounts, dates or descriptions were edited. | All 23 formulas and displayed names match the live SALES lookup. PAYMENTS remains excluded from the recurring tracker. |
| Prospects List, B2B FOLLOW UP `U2:V342` | Missing date inputs return blank. Existing exclusion of zero/negative closing durations through `NA()` is preserved. | All repaired formulas match; the only three remaining N/A values are deliberate original exclusion behavior. |
| Prospects List, B2B FOLLOW UP `Y18` | Conversion uses the labeled Site Visit denominator `Y16`, instead of blank `Y15`, and stays undefined when a denominator is absent/zero. | 4 / 27, approximately 14.81%. |
| Prospects List, 2026 `N11509`, `N15528` | Deleted first follow-up references restored to intact same-row `M` appointment/quotation date plus one day. | All ten downstream follow-up dates now calculate without REF errors. |
| Prospects List, Experiment `A55:A56` | Restored the sequential display-number chain from the previous row. | A54:A60 now follows 46, 47, 48, 49, 50, 51, 52. These display numbers are not persistent business identifiers. |

**18,594 source formula cells were edited and read back with zero formula mismatches.** Only `userEnteredValue` was updated; existing cell formatting, validation, sheet structure and manually entered financial/customer data were preserved. Formula plans record exact old/new expressions before each batch. Every batch was preceded by a fresh read confirming the expected formula and, for name lookups, the expected sale ID.

## Information that cannot be inferred safely

- Owner subsequently confirmed SALES row 531 / CUST527 should be excluded because no Calendar service belongs to that sale. AA531 is now CANCELLED; the existing disposition override excludes it from active sales. Its original PENDING total and source history are retained rather than priced or deleted.
- Owner subsequently confirmed CUST1982 paid the full RM520 through Atome. AC1986 now records RM520 once, AE1986 is zero after reclassification of its prior RM520, X1986 is CLEAR and AG1986 calculates RM0 remaining. AD1986 retains the provider/invoice. Native formatting and the formula were preserved; live readback passed.
- Eight SALES service schedules were independently matched to unique authoritative Calendar records using exact sale identity, phone/invoice and service sequence evidence. Q:R:S dates were corrected for rows 155, 507, 680, 892, 1067, 1079, 1230 and 2191. Row 2061 is a one-session sale: its misplaced third-service email was preserved in the existing contact-cell note, then the non-service date field was cleared. All 39 inspected helper date errors resolved in live readback.
- Prospects 2026 `B14966` had a copied arithmetic formula in the contact column. It is now blank with a note that the telephone number is unknown; enquiry information remains recorded.
- PAYMENTS `B580` contains a telephone number instead of a sale ID. Its failed name lookup is not repaired by guessing a customer. Blank-key helper lookups likewise are not evidence of a paid sale.

These are missing/misplaced source facts, not mechanically repairable formula references. Preserve them as unresolved quality exceptions and exclude unknown amounts/dates from eligible calculations; never use blanket IFERROR-to-zero.

## Evidence and limits

Private originals, repair plans and readback results are in ignored `outputs/source_repair/20261004/`. The final authoritative verification is `verified_source_repair_private.json`; earlier plan/readback files are intermediate evidence. Native formatting was checked through returned Sheets cell metadata, not by a visual browser inspection. This repair does not certify bank settlement, payment-tab freshness, source completeness, treatment attendance, or model accuracy.

Calendar CANCELLED labels mean the original appointment was postponed and do not imply a cancelled contract or debt. Sunday parked appointments can be placeholders while staff await a replacement date. This source-formula work did not reinterpret Calendar events.

## Next refresh

Refresh immutable Bronze snapshots after these edits, rebuild candidate Silver/Gold, and run source-to-Gold reconciliation before publishing. Keep the unknown phone and unlinked refund-needed receipt explicitly represented in the quality record. Do not overwrite historical source evidence or the frozen model's declared training snapshots. The remaining exact cells and resolved financial cases are listed in `CP2_UNRESOLVED_SOURCE_FACTS.md`.
