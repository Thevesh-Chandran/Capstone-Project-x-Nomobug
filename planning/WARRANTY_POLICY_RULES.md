# Confirmed warranty policy rules

These rules were confirmed by the business owner on 21 September 2026 and are
the source of truth for eligibility logic, with the scheduling clarification
confirmed on 1 October 2026 below.

| Client and package | Eligible | Eligibility interpretation |
|---|---:|---|
| Commercial, any package or pest | No | Exclude from warranty-risk cohorts |
| Residential 1x, any pest | No | Exclude from warranty-risk cohorts |
| Residential 3x, any pest | Yes | A claim must be recorded within 30 days after the third service |
| Residential 4x, 6x, or 12x, any pest | Yes | Coverage begins with the first service, remains active through the service programme, and ends 30 days after the final service; multiple claims are allowed during this period |

For residential 3x, completing all three paid services within 14 days is a
scheduling expectation, **not a warranty eligibility condition**. Client
rescheduling or insufficient appointment slots can extend the programme beyond
14 days without removing warranty. The 30-day claim window follows the valid
third-service date recorded in Calendar, excluding cancelled/rescheduled-away
entries; it is not anchored to the originally planned completion date. The
current fixed-horizon anchor logic has no first-to-third-service 14-day cutoff.

Pest type does not change warranty eligibility. Premise values are normalized
to `RESIDENTIAL`, `COMMERCIAL`, `VEHICLE`, or `UNKNOWN`; vehicle, unknown, and
unrecognized package counts remain in a review category rather than being
silently treated as eligible.

The main CP2 prediction target is a recorded corrective Calendar callback within
30 days after a paid service. Callback planning includes recorded discretionary
commercial returns without granting contractual warranty. The fixed prediction
horizon does not shorten the entitlement periods above. See [the model
guide](CP2_START_HERE.md) for the active model roles.

Coverage records must retain repeated 4x/6x/12x claims throughout the service
programme. The [historical interval experiment](archive/model_evaluations/WARRANTY_COVERAGE_MODEL_EVALUATION.md)
preserves that separate modelling investigation. A single post-final-service
binary label would discard valid in-programme claims.
