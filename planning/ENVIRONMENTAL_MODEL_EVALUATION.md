# Environmental factors in the residential 3x warranty-risk experiment

## Decision

Do not promote the current static environmental feature group into
`warranty_risk_residential_3x_30d_v3`. Keep it for descriptive spatial analysis
and future testing. It did not improve pre-2026 validation performance.

## Factors and coverage

The challenger adds elevation, 500-metre relief, and mapped water and forest
proximity/counts. Among 1,335 eligible rows, elevation and relief cover all rows,
water distance covers 1,117, and forest distance covers 242. Missing values are
imputed inside each training fold.

| Feature contract | Pre-2026 mean ROC AUC | Pre-2026 mean AP | Mean Brier |
|---|---:|---:|---:|
| v3 base | 0.5187 | 0.2535 | 0.2143 |
| v3 plus static environment | 0.5162 | 0.2496 | 0.2194 |

On the already-inspected 401-row 2026 diagnostic, the static group changes ROC
AUC from 0.5469 to 0.5530 and average precision from 0.2932 to 0.2998. That small
post-selection gain does not override the weaker development evidence.

## Rainfall and spatial scale

Testing rainfall by area is sensible, but scale must match the source. Current
weather is approximately a 0.1-degree grid, roughly 9–11 km locally. A 1 km or
2 km rainfall radius would repeat the same grid estimate and imply precision the
source does not contain. Spatial clustering may still use smaller radii for
service-location patterns, but it must not be presented as local rainfall.

For a later dashboard, precompute a small set of validated geographic scenarios,
such as weather-grid cell and broader 10 km/20 km neighbourhoods. For each scale
show the eligible denominator, positive count, recurrence-proxy rate, uncertainty,
and model metrics only when both outcome classes have adequate samples. Changing
a radius should select a stored evaluation result; it should not retrain a model
inside the dashboard.

Flooding, drains, standing water, building condition and nearby water are valid
hypotheses. The current mapped-water variable is incomplete and the project has
no verified flood or drainage exposure source, so these factors cannot yet be
used as causal explanations. The target is also a recorded warranty signal, not
confirmed biological recurrence.

Reproduce the static challenger with:

```powershell
python scripts/evaluate_warranty_environmental_factors.py
```
