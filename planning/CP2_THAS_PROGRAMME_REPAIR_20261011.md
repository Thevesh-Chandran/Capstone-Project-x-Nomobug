# THAS service programme correction — 11 October 2026

The owner confirmed that the 24-service Calendar sequence combines the separate 4-service sale (CUST1412) and 20-service sale (CUST1569). The earlier 3-service sale (CUST1167) is separate, as is the earlier one-off sale (CUST981).

## Published correction

- Programme `CONTRACT_0002` contains two sales, 24 paid sessions and RM 3,960 recorded sales. The underlying sales remain separate; their amounts are not duplicated.
- Thirteen exact Calendar identity/date/sequence reviews assign stages 1–4 to the 4-service sale and stages 5–13 to the 20-service sale. The cancelled 12 September slot is excluded; its 19 September replacement is included.
- The programme is commercial and therefore has no contractual warranty under the owner's policy.
- Source Sheets and Calendar events were not edited. Future unreviewed stages require source checks; these dated overrides do not automatically approve every future appointment.

## Verification and limits

Cloud reporting release `20261011103927f93a7b` published on 11 October at 18:47 Malaysia time after its dbt, independent KPI reconciliation and privacy gates passed. Post-publication queries confirmed 24 sessions, two sales, 13 paid visits and the funding allocation above. The full Python suite passed 513 tests (19 existing Rasterio warnings).

This repair changes operational reporting. It does not modify frozen model weights, eligibility transforms, thresholds or historical predictions. The collector's original missed-candidate audit remains preserved. The source ambiguity is resolved, but a late prediction cannot be created and a pooled programme must not be forced into the frozen model's supported scope. Future evaluation must still pass its complete-coverage and integrity gates.

Private row evidence: `outputs/project_value_review/20261011/programme_release_verification_private.json`. Do not publish this evidence as dashboard data.
