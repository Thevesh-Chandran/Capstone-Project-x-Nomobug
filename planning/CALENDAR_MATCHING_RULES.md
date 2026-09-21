# Calendar-to-customer matching rules

These rules were confirmed by the business owner on 13 September 2026. They
describe record linkage and warranty classification; they do not authorise
editing the source Sheets or Calendars.

## Operational flow

1. A prospect first appears in the Prospects `2026` tab with a phone number when
   one is available.
2. When details are requested and a payment link is sent, the opportunity is
   recorded in `PAYMENT LINK` using the phone number. `WON` means the link
   opportunity was successfully paid/closed; `PENDING` remains open. The source
   status can be missed, so it is a funnel signal rather than the only sale
   authority.
3. Once a package is chosen, the customer is recorded in `SALES`, and the
   service event is created in Google Calendar. The Calendar event start is the
   operational service date.
4. Money received is recorded separately in `PAYMENTS`, one receipt row at a
   time. A single sales/customer ID can therefore occur on multiple payment
   rows.
5. A persistent pest problem after the eligible package completion can create a
   `WARRANTY CLAIM` row. If eradication still fails after complimentary service,
   a `REFUND` row may be recorded.

## Calendar event interpretation

Titles commonly contain the pest/package and session sequence, for example
`GPC 1/3`. The description is the stronger matching payload and may contain:
premise name, address, package, problem, invoice, email and phone number.
The raw description remains restricted to Bronze. Silver uses parsed fields and
does not expose the raw description or location.

Some descriptions are HTML (`<p>`, `<br>`, mailto links). Block tags must be
converted to line breaks before parsing, otherwise phone/email/address labels
are lost. Multiple phones in a SALES cell are compared separately. Generic
payment labels such as `BANK TRF` and `JOM PAY` are not unique invoice IDs.

## Matching priority

Use the strongest available key and retain a confidence label:

1. Exact invoice or customer ID parsed from the description matched to SALES.
2. Normalised phone number matched to PAYMENT LINK, Prospects or SALES.
3. Exact email matched to SALES when it produces one candidate.
4. Exact normalized address matched to SALES when it produces one candidate.
5. Exact WhatsApp/Meta username when it is unique and consistently recorded.
6. Exact name plus package/address/date context.
7. Name alone is never an automatic match.

When methods disagree, evaluate only the strongest available tier first; a
weak name/address hit must not make a unique phone match ambiguous. One phone
shared by multiple SALES packages is still ambiguous until package/date or
other evidence separates them. For example, Maestro's earlier monthly records
share a phone and remain under review; later records with different phones
resolve to their respective SALES rows.

For shared-phone packages, the strongest date/session rule uses a parseable
SALES closed date, a Calendar title package total equal to SALES `Total Session`,
and a confirmed `1/N` Calendar anchor on the same phone after that sale's
closed date and before the candidate event. Where both Calendar addresses are
present, they must agree. Choose the single most recent eligible sale.

If the anchor is absent, a secondary closed-date evidence rule may still select
one Sale, but only when the Sale closed on or before the Calendar date and a
unique title-customer, address, or title-session clue agrees. A direct unique
phone/invoice/email match is never overridden by this fallback. Same-day ties,
missing/invalid closed dates, and no independent clue remain ambiguous. These
are medium-confidence package links, not proof that the visit was completed.
CC's 1-session 2025 sale, 48-session February 2025 sale, and restarted
48-session April 2026 sale are regression-tested examples.

Calendar chronology is also used as a package-lineage resolver when a Sales
closed date is missing or the Calendar event was scheduled before that row was
closed. For a shared phone, the matcher follows each candidate's confirmed
`1/N` anchor, requires `N` to agree with the Sales session total when available,
and assigns a later warranty/complimentary/extra event to the candidate with
the single latest eligible anchor. This resolver does not require the address
to match: the same customer may be servicing a different property. It resolves
the CoreHaus `1/1` versus later `1/3`, Azam's later `1/4` package, Sarimah's
`4/4`, Noor Shazrina's `1/7` lineage, and Nurasikin's House 1/House 2
packages. Nurasikin is resolved from normalized customer-name/property markers
and Calendar address context; the address is allowed to differ from another
property's address. If a later numbered event changes its displayed total (for
example `8/10` after a verified `1/7` anchor), the matcher treats it as a
continuation of the existing package when no separate sale exists. FAFA's
`8/10` follows its existing 7-session sale in the current snapshot. The future
`9/10` event can be checked after the next Calendar refresh. The explicit
`4/3` and `5/3` warranty visits remain with the earlier 3-session sale.

Ambiguous and unmatched events remain in the data with `match_status` and
`match_confidence`; no customer identity is guessed. A Calendar event is not
silently deduplicated with another package or person.

Calendar entries that are cancelled, consultation-only or otherwise outside the
service-candidate categories remain in the matching view but are marked with a
`matching_scope` of `non_service_event`. They are not counted as failed customer
links in operational coverage metrics.

## Service and warranty rules

- `GPC 1/3`, `2/3`, `3/3` and equivalent sequences represent package sessions;
  the sequence is parsed from the title when it is present.
- Titles such as `4/3`, `5/3`, `6/3`, etc. are warranty/claim visits after the
  purchased package. They represent a client reporting that pests returned
  within the applicable warranty window, even when the Calendar title says
  `COMPLIMENTARY`; the model marks them `post_package_sequence` warranty
  candidates. There is no two-free-visit cap in the model.
- Explicit `WARRANTY`, `CLAIM` or `CALLBACK` titles are also warranty-claim
  candidates. This includes free follow-up services attached to 6-session or
  12-session/yearly packages when pests return during the covered period.
  Calendar supplies the operational date for each visit and any reschedule.
- `WARRANTY CLAIM` remains authoritative for the formal claim record and
  technician/refund fields. The Calendar-derived flag is the operational
  warranty-visit signal used for service timelines and spatial analysis; it is
  not proof that a treatment was completed or that a claim row was recorded.
- `WARRANTY CLAIM` is authoritative for the recorded claim and technician
  fields, not the final visit schedule or a maximum extra-visit count. The
  `warranty_calendar_visits` view joins each formal claim to every matched
  Calendar service candidate for that SALES ID. This is a same-sale timeline,
  not a claim-to-visit attribution: count distinct formal claim IDs for claims,
  and do not count joined rows as warranty visits. Calendar supplies the
  scheduled/recorded visit date; completion still needs independent evidence.
- `REFUND` is a separate outcome after the pest could not be eradicated despite
  complimentary service. Refunds must not be counted as new sales.

## Grain and financial safeguards

- SALES grain: one package/sale row; Customer ID is a sale/package identifier,
  not a permanent person identifier.
- PAYMENTS grain: one receipt row. Combined references are linked to multiple
  sales IDs but their amount is not allocated to each sale without evidence.
- Commercial Clients and Recurring Payments support reconciliation and are not
  additional SALES or PAYMENTS facts.
- Calendar service dates replace stale SALES service-date columns for operational
  timing; scheduled or cancelled events are not silently labelled completed.
