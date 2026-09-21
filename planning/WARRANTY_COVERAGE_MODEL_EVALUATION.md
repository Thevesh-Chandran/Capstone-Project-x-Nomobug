# Residential 4x/6x/12x warranty coverage model evaluation

## Dataset contract

The dataset contains one row per mature coverage interval beginning at each
recorded base service. Pre-final intervals end the day before the next service;
the final interval ends 30 days after the final service. Multiple recorded
warranty signals are retained. Commercial, residential 1x and residential 3x
packages are excluded.

There are 364 intervals across 146 packages and 50 positive intervals. Eleven
packages have multiple recorded claims. Prediction-safe history now records the
number of earlier claims and services and time since the previous claim/service.

## Validation design

Two complementary checks are used:

1. Temporal evaluation trains on 2024–2025 and reports on 2026.
2. Five-fold stratified grouped validation keeps every interval from a package
   in one fold, preventing the same package from appearing on both sides.

The 2026 confidence intervals use 1,000 package-level bootstrap samples.

## Selected experimental challenger

The history-only L2 logistic model is selected. It has the best grouped average
precision and does not depend on environmental variables that fail to generalize.

| Validation | ROC AUC | Average precision | Brier score |
|---|---:|---:|---:|
| Package-grouped 5-fold mean | 0.6522 | 0.2907 | 0.2254 |
| 2026 temporal evaluation | 0.6857 | 0.3215 | 0.2028 |

The 2026 uncertainty is wide:

- ROC AUC 95% package-bootstrap interval: 0.516–0.817.
- Average precision interval: 0.148–0.564.
- Brier interval: 0.154–0.258.

This remains experimental and must not drive automated customer decisions.

## Environmental stability

| Feature contract with prior history | Grouped mean ROC AUC | Grouped mean AP | Grouped mean Brier |
|---|---:|---:|---:|
| History only | **0.6522** | **0.2907** | 0.2254 |
| History plus prior weather | 0.6517 | 0.2677 | **0.2246** |
| History plus HOTOSM waterways | 0.5424 | 0.2132 | 0.2446 |
| History plus weather and HOTOSM | 0.5284 | 0.1932 | 0.2491 |

The earlier apparent HOTOSM improvement disappears after adding prior history
and separating packages. Weather also fails to improve grouped average precision.
Both remain descriptive context rather than selected model features.

## Package-specific support

| Package | 2026 rows | Positives | ROC AUC | Average precision | Supported |
|---|---:|---:|---:|---:|---:|
| 4x | 78 | 15 | 0.6720 | 0.3753 | Yes, experimental |
| 6x | 39 | 3 | 0.4259 | 0.0939 | No |
| 12x | 29 | 2 | 0.4444 | 0.0972 | No |

Only the 4x segment meets the minimum reporting rule. The combined model may be
shown as capstone feasibility evidence, while 6x and 12x remain descriptive.

The target is a recorded Calendar warranty signal, not confirmed biological
recurrence or proof of treatment failure.
