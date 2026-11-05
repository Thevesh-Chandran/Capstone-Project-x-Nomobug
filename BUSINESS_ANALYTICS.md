# Business analytics

Business reporting uses actual published source records. The 100-service historical model evaluation remains a separate tool called **Model test by area**.

- Sales: one included Sales row, counted once at its recorded closing date. Missing dates stay in coverage and are excluded from date-filtered totals. Sales are package prices, not received cash or profit.
- Purchases and programmes: owner-confirmed 1x plus Upsell 2x and 4x plus 20x sales remain separate financial rows but one programme each.
- Customer groups: exact normalized name plus one valid Malaysian phone number, or an exact commercial name and address. Explicit billing annotations are removed from names; branch labels remain. Missing/ambiguous contacts remain separate. This is conservative matching, not a verified customer master.
- Repeat customers: at least two separate programmes for an exact matched identity. Appointments, instalments and warranty visits do not create another purchase.
- Districts: official DOSM polygons with coordinate uncertainty and boundary margins. Sales require an exact address hash match to an eligible existing Calendar geocode. A sale is never assigned merely because it links to a Calendar visit. Unknown locations remain **Unassigned**.
- Appointments: eligible Calendar service records. A booking is not proof of completed treatment.
- Contract balances: Sales deposit plus cumulative balance paid. The Payments tab is not settlement evidence. Reminder dates do not prove payment, overdue debt or a sent reminder.

Run `python -m scripts.release_business_analytics --publish` after a validated reporting release. It resolves the immutable release from published views, checks Silver/Gold consistency, bounds every BigQuery query at 100 MiB and reconciles 2026 sales against published Gold. Private exports go only into ignored `outputs/business_implementation/current`.

Aggregate BigQuery views: `gold.dashboard_business_sales`, `gold.dashboard_business_services`, `gold.dashboard_business_customers`. They contain no customer names, phones, addresses or individual sale identifiers. Customer profiles and histories stay in the existing private portal and private runtime bucket. Search uses POST so names do not enter request URLs.

Daily reporting can export both the existing aggregate snapshot and the private business tool snapshot when `CP2_PORTAL_GCS_URI` is configured. A failed candidate validation preserves the last approved reporting release. Portal export failures are recorded separately and do not claim that an already-published Gold release failed.

The frozen prediction model, thresholds and prospective prediction ledger are not changed by business analytics.
