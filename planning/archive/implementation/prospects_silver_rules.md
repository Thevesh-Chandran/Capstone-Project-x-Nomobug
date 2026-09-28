> Archived evidence or implementation history. Its dated status and model choices are not current instructions. Start with [the current model guide](../../CP2_START_HERE.md).

# Prospects 2026: confirmed business rules

## Grain and preservation

Preserve raw source values and snapshot/row lineage. A prospect row represents an enquiry record, not a unique customer. Repeated phone numbers can represent repeat conversations.
Placeholder rows remain in Bronze and must be distinguished from prospect candidates.

## Dates

The owner confirmed that the 2026 tab contains only 2026 records.
ENGAGE records the date staff first replied, not the inbound message timestamp.
Automatic follow-up dates indicate scheduled contact dates, not completed contacts.
Use 2026 for yearless ENGAGE dates after validating day/month values.
Do not force follow-up dates into 2026 at a December/January boundary; verify the source formula or underlying date before resolving rollover.

## Acquisition source

The platform column mixes channels and campaign identifiers. Preserve both detail and derived grouping.
B-prefixed ad codes identify business-targeted ads. They do not establish customer type.
ADS-, A-, and CA-prefixed codes identify regular ads; their social platform is not established by that code alone.
Website, Instagram and Facebook may be recorded when staff know the source but not the campaign.
NA means unknown acquisition source and is a legitimate operational state.
JESS and SEMUT labels are unresolved; the owner suspects errors or informal markings. Retain and flag them.

Implementation: source grouping uses full code patterns, not just a first-letter
match. Generic ADS is UNSPECIFIED_AD. Blank is MISSING; NA is UNKNOWN; other
unmapped labels are UNRESOLVED. Spelling aliases WBSITE/WEBSIITE, FB and REFERAL
are normalized while preserving raw values. GOOGLE does not imply paid search;
TIKTOK does not imply a paid ad. Campaign grouping never overwrites customer type.

## Pest category

GPC means general pest control; ANAI ANAI identifies termite enquiries.
CST, N and WD remain unknown and flagged, as explicitly confirmed by the owner.
BEDBUGS grouping under GPC is a proposed mapping based on the owner's general definition; preserve the original label.

## Sales and recordkeeping

A successful sale requires a booked slot and payment made; full payment was not specified.
Session and Payment workbook Sales/Payments records are the basis for sales reconciliation; Calendar supplies accurate service-slot dates.
Prospects CLOSED includes both won and lost conversations.
WON in remarks is a supporting recorded-win signal and may be missing because staff forget to update it.
Never infer a lost sale from absence of WON. Reconcile downstream records first.

Management reporting should measure how consistently confirmed, matched sales have WON recorded in Prospects.
Report unmatched and ambiguous matches separately. Repeat enquiries must not all inherit a win from a shared phone.
Update-rate denominator: confirmed sales with an unambiguous prospect match. Numerator: those with the matched prospect updated to WON.
Attribution, matching window and allowed update delay remain to be defined before implementation of this KPI.
