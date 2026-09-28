# Analytics ML experiment layer

`warranty_risk_3session_dataset` is a deliberately narrow experiment cohort:

- one included SALES package with exactly three recorded sessions;
- one unambiguous, matched Calendar `3/3` anchor on or after the sale date;
- a fully observed 30-day outcome window for eligible residential 3x packages;
- target = a later recorded Calendar warranty-claim signal within that window.

Prediction time is immediately after the recorded `3/3` event. Features are
restricted to information available by then. The label is operational recording
evidence, not proof that treatment was completed or that pests biologically
recurred. Customer names, phones, emails and addresses are not projected.

Run `python scripts/build_ml_foundation.py` to build/test the cohort. The baseline
script compares simple model and horizon choices. The frozen v2 experiment is
then produced by `python scripts/tune_warranty_risk_model.py`, which selects among
regularised logistic regression and small tree models using pre-2026
walk-forward folds. The mature 2026 cohort is reporting evidence, not a new model
selection set. Outputs are experimental and must not automate service, customer,
employee or scheduling decisions.

The v2 model includes only prediction-time-safe weather history. Event-day
weather, team identity, salesperson/acquisition fields, payment behaviour and
static environmental context are excluded from the selected feature contract.
Static environmental context is evaluated only as a grouped challenger because
its forest and water coverage is uneven and the development sample is small.
