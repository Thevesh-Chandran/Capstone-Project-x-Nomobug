# Confirmed warranty policy rules

These rules were confirmed by the business owner on 21 September 2026 and are
the source of truth for eligibility logic.

| Client and package | Eligible | Model treatment |
|---|---:|---|
| Commercial, any package or pest | No | Exclude from warranty-risk cohorts |
| Residential 1x, any pest | No | Exclude from warranty-risk cohorts |
| Residential 3x, any pest | Yes | A claim must be recorded within 30 days after the third service; this is the current v3 model population |
| Residential 4x, 6x, or 12x, any pest | Yes | Coverage begins with the first service, remains active through the service programme, and ends 30 days after the final service; multiple claims are allowed during this period |

Pest type does not change warranty eligibility. Premise values are normalized
to `RESIDENTIAL`, `COMMERCIAL`, `VEHICLE`, or `UNKNOWN`; vehicle, unknown, and
unrecognized package counts remain in a review category rather than being
silently treated as eligible.

The current target is a recorded Calendar warranty signal. It is an operational
proxy and does not prove biological pest recurrence.

The 4x/6x/12x policy should be modelled as repeated time intervals or service
episodes because a client may claim more than once while coverage is active. A
single post-final-service binary target would discard valid in-programme claims.
