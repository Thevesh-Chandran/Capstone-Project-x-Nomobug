> Archived evidence or implementation history. Its dated status and model choices are not current instructions. Start with [the current model guide](../../CP2_START_HERE.md).

# Operational Silver: complete source snapshot batch

```powershell
python scripts/build_operational_silver.py --build
```

Without --build, the runner compiles and runs read-only SQL validation against
the fixed verified Bronze tables, inlining model dependencies so no views change.
With --build, it creates/replaces nine operational views and runs 13 operational
data tests. Prospects is
excluded by tag selection. Its current lineage is read solely because dbt parses
the whole project. The Prospects refresh runner now selects only its own model
and its independent mapping test, not this operational batch.

| View | Grain and scope |
|---|---|
| silver.b2b_follow_up | Every raw B2B row plus snapshot-row key and basic labels |
| silver.sales | Every raw sales row plus parsed sales-record ID and package total |
| silver.payments | Every raw payment row plus amount and whole-field ID parsing |
| silver.payment_link | Every payment-link row plus conservative WON/PENDING outcome flag |
| silver.warranty_claim | Every claim row plus raw date/customer/technician fields |
| silver.commercial_clients | Every supporting commercial row; not an extra sale fact |
| silver.refund | Every refund row with bank-account/bank-name columns omitted |
| silver.recurring_payments | Every recurring billing row; not an extra payment fact |
| silver.payment_sales_links | One unique payment/sales-record pair; amount intentionally absent |

All original positional columns remain on the first three views. IDs use the
immutable snapshot table plus sheet row, not permanent transaction identifiers.
Payment links deduplicate repeated references inside one field only, not payment
records. Missing or ambiguous Sales matches remain labelled; allocated amounts
remain null. Unknown ID text stays on payments even when it yields no links.

Amounts use BigQuery NUMERIC, not float. Invalid values stay null and flagged,
not zero. Dates remain raw pending validation of source formats and business
meaning. Sales service dates are not authoritative; Calendar will supply those.
Neither #VALUE! field is mapped as balance until its position is confirmed.

These are preserved-and-flagged Silver views, NOT dashboard-ready financial
facts. Do not sum all raw candidates as revenue or cash received before resolving
test rows, repeated receipts and source coverage. Absence of a returning flag
does not prove a new customer. A matching link does not establish completed care.

Sources are fixed in operational_sources.yml and metadata-checked by the runner;
they do not automatically follow new Bronze uploads. A later refresh design must
update these identities together. No schedule, deletion or Neon writes.

Builds are not atomic across views. A failure can leave changed views: stop and
review the error; do not publish downstream results. No automatic rollback yet.

Send the final dbt summary and OPERATIONAL SILVER BUILD PASS, or the first error.
