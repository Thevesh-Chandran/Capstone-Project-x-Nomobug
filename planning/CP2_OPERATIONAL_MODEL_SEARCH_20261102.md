# Operational model search, 2 November 2026

Goal: find a model that performs clearly better than a simple alternative, answers a question staff can act on, and can be scored inside the portal from its own published snapshot. The frozen 30-day pest-return experiment, its threshold and its future evaluation are unchanged.

Data: current private portal snapshot (release `cp2r_20261027220023217d5b`): 2,538 sales, 8,086 Calendar appointments (6,479 with a location, 1,404 properties), 2,312 customer groups. Klang Valley daily rain from the Open-Meteo grid file was offered as an extra input.

## What was tried

| Question | Configurations | Choice rule | Held-out result | Verdict |
|---|---:|---|---|---|
| Bookings next week (weekly count) | 28 models + 4 baselines | Validation MAE, Mar to Jun 2026 | Extra Trees 9.71 vs 13-week average 9.23 (5% worse) | No gain |
| Warranty visits next week | 28 + 4 | same | Ridge 3.60 vs 3.16 (14% worse) | No gain |
| Paid service visits next week | 28 + 4 | same | Extra Trees 9.71 vs 8.55 (14% worse) | No gain |
| New sales next week | 28 + 4 | same | Ridge 4.80 vs 4.84 (1% better) | No real gain |
| Sales value next week | 28 + 4 | same | Ridge RM 5,208 vs RM 4,926 (6% worse) | No gain |
| Time to repeat purchase (survival) | 51 (Cox, random survival forest, gradient-boosted survival × 3 input sets) | 5-fold CV C-index on customers before 2026 | C-index 0.764 vs deployed repeat90 ranking 0.773 | Matches, does not beat, the current model |
| **Warranty visit within 30 days of a paid visit, per property** | 16 + 24 robustness variants | Validation average precision, Jan to Apr 2026 | **AUC 0.77, AP 0.30 vs base rate 0.10; top 20% of visits hold 52% of warranty calls (2.6x)**; simple past-warranty-rate rule AUC 0.55 | **Selected** |

Weekly models used 107 weeks (Oct 2024 to Oct 2026): 7 model families (ridge, strong ridge, Poisson, random forest, Extra Trees, gradient boosting, Poisson gradient boosting) × 4 input sets (own lags; plus calendar, holidays and Ramadan; plus related series; plus rain and humidity), refitted at every weekly origin. With two years of weekly history, a 13-week moving average is very hard to beat. The existing planning forecasts do beat their baselines because they use appointments already booked ahead, which this snapshot cannot reconstruct historically. Extra inputs (holidays, rain, cross-series) did not help.

Repeat purchase is rare (145 repeats among 1,956 first-time customers since Oct 2024; 7% within a year, 20% for commercial customers). The survival model ranks about as well as the deployed 90-day ranking. It adds timing: the median repeat comes 88 days after the first purchase (quartiles 26 and 236 days).

## Selected model: property warranty risk (`warranty_risk_v1`)

Question: after a paid service visit, will the same property need a warranty visit within 30 days?

- Rows: 4,911 paid visits at located properties, Oct 2024 to Sep 2026; 10.3% followed by a warranty visit within 30 days.
- Inputs: the property's own visit history before the scored visit (earlier visits, earlier paid and warranty visits, warranty rate, warranty and all visits in the last 90 days, days since the previous visit, first visit flag). Pest, district, sale details and rain were tried and did not improve validation results.
- Model: Extra Trees, 200 trees, minimum leaf 20, half the inputs per split, balanced classes, then Platt calibration fitted on validation scores.
- Split: development before Jan 2026; validation Jan to Apr 2026 (configuration choice); test May to Sep 2026 (1,104 visits, 107 warranty calls), scored once with a development+validation fit.
- Test: ROC AUC 0.767, average precision 0.300 (base 0.097), Brier 0.078 vs 0.088 for a constant. Flagging the top 20% catches 52% of warranty calls at 25% precision (2.6x lift). Calibrated expected calls 106.7 vs 107 recorded.
- Robustness: across 24 leaf/feature variants, test AUC stayed between 0.74 and 0.78. The test grid was inspected after the choice and was not used to choose.

Compared with the frozen pest-return reference (Q4 study: precision 31.5%, recall 56.8% at about 20% prevalence, 1.6x lift), this model reaches a higher lift on a lower-prevalence population. The populations and labels differ, so the figures are not a direct replacement claim.

Limits: a Calendar warranty signal is not proof of treatment failure; the snapshot keeps surviving appointments only; flagged properties mostly will not call back (25% precision). Treat it as a ranking for proactive check-ins, not a prediction for any single customer.

## In the portal

- `webapp/warranty_risk.py` scores every located property with a paid visit in the last 30 days and no warranty visit recorded since. It adjusts each chance for the days already passed using the observed timing of warranty calls.
- New page **Analysis › Warranty risk** lists properties to check first, the expected warranty visits in the next 30 days, and the test evidence.
- Recommendations gains the option "Check in early with N high-risk properties", ranked with the other options.
- Model file: `webapp/models/warranty_risk_v1.json` (portable trees, no scikit-learn at runtime). Retrain with `python scripts/train_warranty_risk.py --data <runtime folder>`.

Study code: `scripts/research_operational_models_20261102.py`, `scripts/research_repeat_survival_20261102.py`, `scripts/research_property_warranty_20261102.py`.
