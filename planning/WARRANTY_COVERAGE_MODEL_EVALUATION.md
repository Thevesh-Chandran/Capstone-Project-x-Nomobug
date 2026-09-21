# Residential 4x/6x/12x warranty coverage feasibility

## Dataset contract

The dataset contains one row per mature interval beginning at each recorded base
service. For services before the final service, the interval ends the day before
the next service. The final interval ends 30 days after the final service. Every
recorded Calendar warranty signal in an interval is counted, so repeated claims
are retained.

Commercial clients and residential 1x/3x packages are excluded. The label is an
operational Calendar signal and does not prove biological recurrence or treatment
failure.

## Coverage

| Package | Development intervals | 2026 intervals | Recorded claims |
|---|---:|---:|---:|
| 4x | 145 | 78 | 46 |
| 6x | 66 | 39 | 6 |
| 12x | 7 | 29 | 2 |

There are 364 mature intervals across 146 distinct packages. Eleven packages
have more than one recorded claim. The 6x and especially 12x samples are too
small for dependable package-specific models.

## Initial 2026 benchmark

The development period has 218 intervals and 30 positive intervals. The 2026
period has 146 intervals and 20 positives, a 13.7% positive rate.

| Feature group | ROC AUC | Average precision | Brier score |
|---|---:|---:|---:|
| Base, without weather | 0.6607 | 0.2473 | 0.2133 |
| Base plus prior weather | 0.6440 | 0.2582 | 0.2227 |

Prior weather slightly raises average precision but lowers ROC AUC and worsens
the Brier score. With only 50 positive development/reporting intervals combined,
this is exploratory evidence and does not justify operational scoring.

## Rainfall and geographic scale

Geohash sensitivity was calculated at broad, area, and local scales. Only 7 of
104 area-period groups meet the minimum of 30 intervals, 5 positives, and 5
negatives. No local approximately 5 km group is large enough for a performance
metric, and the weather source is coarser at approximately 9–11 km.

Among supported groups, rainfall/target correlations are small and inconsistent.
The broad-area correlation changes from -0.111 in development to +0.045 in 2026.
There is therefore no stable evidence that more rainfall predicts more recorded
warranty claims in this sample.

Flooding, drains, standing water and mapped-water proximity remain reasonable
hypotheses for future data collection. They cannot currently be presented as
causal explanations.

Reproduce with:

```powershell
python scripts/evaluate_warranty_coverage_episodes.py
```
