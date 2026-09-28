> Archived evidence or implementation history. Its dated status and model choices are not current instructions. Start with [the current model guide](../../CP2_START_HERE.md).

# Calendar location validation gate

Scope: the pinned Calendar Bronze snapshot and 2026 confirmed service-like
events. Reproduce the first-line aggregate with
`python scripts/inspect_weather_location_readiness.py`, then the cautious
multi-line check with `python scripts/inspect_calendar_address_blocks.py`.
An event is not proof that a treatment was completed.

## Current evidence (15 September 2026)

- 2,776 Calendar event rows, with no expansion of event grain.
- 2,776 have extracted address text. This is text recognition, not a verified
  service-property location.
- 2,011 have a five-digit token on the extracted address line. The other 765
  still have address text; some addresses continue on subsequent lines.
- 48 of those 765 have a five-digit token elsewhere in the description. It
  may be in a following address line or an unrelated field. A local parser
  found an address-like continuation containing a five-digit token for 30
  events; all 30 continuation lines were inspected and looked like address
  lines. This raises postcode-shaped address-block coverage to 2,041/2,776;
  735 have no such token in their cautious block. These are event counts, not
  distinct properties or validated postcodes.
- Seven events with a token in both the Calendar and linked SALES address
  disagree in the current pinned match view. This is a review queue, not seven
  wrong matches. Two Kittys Care Putrajaya visits were previously linked to
  a Kajang sale; the owner confirmed separate location-specific sales, and a
  general phone + title-qualifier + session-total + closing-date rule now
  links those 2/3 and 3/3 visits to the earlier three-session Putrajaya sale
  CUST1612. The later 1/4 through 3/4 Putrajaya sequence remains on CUST1686.
  A follow-up private check of all nine SALES rows sharing that phone found
  the other linked Kajang, Cheras, Gombak and Setapak sequences on their
  respective location-specific sales; phone alone was not treated as a
  customer-location key.
  Three Ahmad Tarmizi visits have a four-session title and newer four-session
  sale; the earlier sale has only three sessions, so their different Calendar
  address does not justify moving them to that older package. The actual visit
  property remains the Calendar address. Fawwaz (two events) and Punita (one
  event) retain owner-confirmed sale assignments despite different visit
  addresses. The remaining Nas event has otherwise similar lot/neighbourhood
  text but 51000 in Calendar versus 51100 in SALES; this could be a typo or a
  distinct unit, and is not verified. Never overwrite Calendar visit location
  from SALES or treat a postcode-shaped disagreement as a failed match.
- The private, read-only diagnostic is
  `python scripts/inspect_calendar_location_disagreements.py`. It validates
  event grain and caps billed query bytes; raw addresses print only locally.
- Conservative punctuation/case/whitespace normalization yields 887 candidate
  address strings across 2,776 events: 169 occur once and 2,607 events sit on
  repeated strings. These are not 887 verified unique properties. One location
  can have several spellings; repeated visits and packages can share one
  location.
- 913 linked SALES IDs have at least one candidate address string. Thirteen
  SALES IDs currently occur with multiple strings; 35 candidate strings occur
  under multiple SALES IDs. These counts changed after matching improvements;
  they do not establish customer or property counts.
- SALES closing dates, package counts, event dates, session sequences, names
  and address evidence showed two avoidable cross-sale assignments. The
  generalized matcher now weighs available name and address agreement before
  the latest eligible close date. Three first-house visits moved from CUST1852
  to CUST1772; two Shaun visits moved from CUST2320 to CUST2302. The separate
  second-house and Lau event sequences remain with CUST1852 and CUST2320.
  The Calendar dbt build passed 13 steps, including source-backed regression
  expectations and the existing grain checks.
- Owner-confirmed unit distinctions and compound-package counting resolved
  further cases: Ikhmal's House 2 warranty now links to CUST811, and Fawwaz's
  July House & Car 3x visits link to the newer six-session CUST2198 sale. The
  newer closing date and package sequence keep Punita's July 2/3 visit on
  CUST2264 even though its Calendar address is the older-sale location.
  Syed's July House 2 3/3 event stays with CUST2159: House 1's 3/3 was already
  recorded before the House 2 sale closed. The owner confirmed that the July
  visit physically serviced House 1 because that house had pests, although the
  visit belongs to the House 2 package. The Calendar description's House 1
  address is therefore the actual service location for that visit; the title
  identifies the package sequence, not necessarily the physical property.
- The remaining multi-string SALES IDs include both formatting variants and
  materially different premises/units/localities. A different location does
  not automatically mean a wrong link: one sale explicitly covers three units.
  The review script prints SALES details, date/title boundaries and match
  tiers only with the private
  `--review-multi-string-sales` flag; default output remains aggregate-only.
- `python scripts/inspect_calendar_competing_sales.py <SALE_ID> ...`
  reproduces the private phone-sharing and event-sequence evidence in the
  terminal.
- The privacy-safe address cleaner now identifies 787 distinct candidate
  strings representing 2,471/2,776 service-like event rows. Geoapify returned
  782 unique cached results; five provider requests remain unresolved after
  network errors. Current quality rules accept 606 candidate strings covering
  1,857 events: 29 precise, 414 street and 158 postcode-area candidates.
  Another 181 strings/601 events remain manual review. The active cache was
  migrated to sanitized address keys; its prior form is preserved in a private,
  git-ignored backup.
- A Geoapify pilot is prepared in `scripts/pilot_geoapify_calendar.py`. Its
  read-only plan found 532 distinct conservative candidate address strings
  across the 2,776 visits. The pilot defaults to plan-only, rejects obvious
  contact-bearing or ambiguous address lines, de-duplicates inputs, and caps
  execution at five new requests by default. Larger deliberate runs remain
  capped at 600 and rate-limited below five requests per second.
  Results go only to git-ignored
  `data/processed/geocoding/geoapify_pilot_v2.jsonl` for private review. The
  sanitized accepted subset is loaded at event grain to
  `quality.calendar_event_geocodes_2026_v2`; the earlier 1,265-row table is
  retained for rollback. BigQuery contains no raw address/contact values in
  these Quality tables. Even a high provider confidence is not proof of the
  actual service property or exact entrance.
- Open-Meteo ECMWF IFS daily reanalysis is cached for 419/509 distinct accepted
  coordinate points, covering 1 January through 14 September 2026. The other
  90 locations remain pending after HTTP 429 responses and can resume without
  duplicate calls. The verified 107,683 rows are stored in the partitioned,
  clustered `quality.open_meteo_weather_daily_2026_v1` table. Weather describes
  an approximately 9 km model grid, not a house-level observation.
- Fine heatmap coverage is 215/1,202 Calendar warranty-claim candidates. These
  include explicit warranty labels and post-package sequences such as 4/3 and
  5/3, including titles written as complimentary. Event-day weather is
  available for 192 candidates; 183 have a complete prior 14-day window.
  Missing coverage must be shown with every hotspot/weather result. DBSCAN
  sensitivity currently yields 18 clusters at 1 km, 27 at 2 km
  and 10 at 5 km. These are analytical sensitivity radii, not biological pest
  spread. Area repeat shares use scheduled service entries as the denominator
  and flag cells with fewer than five events.

## Safe next gates

1. Keep the Calendar event as the unit of location evidence. Distinguish
   customer identity from service property; the same customer can have more
   than one house.
2. The local address-block prototype now follows adjacent address-like lines
   and stops before contact, invoice, package, treatment or notes. It does not
   feed SALES matching or a warehouse model. Continue testing against mixed
   formats before treating its candidate blocks as service-property locations.
3. Candidate strings are grouped locally for review, not deduplicated into
   customers or final properties. Model service location at Calendar-event
   grain separately from the SALES package and its recorded property. Syed's
   July visit demonstrates why a package can be serviced at a different house.
   A distinct address alone must not cause relinking. Validate samples across labelled,
   unlabelled, postcode-on-next-line and no-postcode formats before assigning
   coordinates. Use
   `python scripts/inspect_calendar_address_blocks.py --review-multi-string-sales`
   only in a private terminal if raw address variants are needed.
4. The owner selected Geoapify's free geocoding plan for the prototype. Add
   `NOMOBUG_GEOAPIFY_API_KEY` only to private `.env`, then run the capped pilot
   deliberately with `python scripts/pilot_geoapify_calendar.py --execute`.
   Do not geocode automatically or send all addresses in one batch. Review
   provider confidence, match type, country, postcode and coordinates before
   treating any result as a service property. Preserve Geoapify/OpenStreetMap
   attribution when results are reused.
5. Once coordinates are validated, join historical weather by property and
   service date, with explicit lag windows. Define repeat-pest outcomes from
   complaints or extra visits, not normal package sessions alone. Only then
   test a distance-based hotspot radius and sensitivity ranges.

Missing postcode alone is not a customer-matching failure and does not prove
an address cannot be geocoded. A five-digit pattern alone is not a validated
postcode, and an extracted address is not a coordinate.
