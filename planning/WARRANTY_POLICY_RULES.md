# Confirmed warranty policy rules

These rules were confirmed by the business owner on 21 September 2026 and are
the source of truth for eligibility logic.

| Client and package | Eligible | Eligibility interpretation |
|---|---:|---|
| Commercial, any package or pest | No | Exclude from warranty-risk cohorts |
| Residential 1x, any pest | No | Exclude from warranty-risk cohorts |
| Residential 3x, any pest | Yes | A claim must be recorded within 30 days after the third service |
| Residential 4x, 6x, or 12x, any pest | Yes | Coverage begins with the first service, remains active through the service programme, and ends 30 days after the final service; multiple claims are allowed during this period |

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
