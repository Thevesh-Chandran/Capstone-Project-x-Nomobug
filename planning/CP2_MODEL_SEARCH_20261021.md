# Model research addendum — 21 October 2026

Start with `outputs/model_validation/20261021_management_model_search/Management_Model_Search.html` or its Jupyter notebook. The share ZIP contains aggregate results only. This addendum updates modelling evidence; it is not a new cloud health, billing, dashboard or future-cohort acceptance check.

## Main finding

Two short-term planning candidates passed the declared exploratory historical gate:

| Question | Selected model | Model MAE | Strong baseline MAE | Later assessment |
|---|---|---:|---:|---|
| Calendar booking entries in the next two weeks | Extra Trees, 36 inputs | 12.76 entries | 20.73 entries | 13 overlapping origins, July–October |
| Booked appointment hours in the next week | Ridge, 32 inputs | 8.97 hours | 11.77 hours | 14 origins, July–October |

These correspond to 38.5% and 23.8% lower absolute error. They are not classification accuracy percentages. Their WAPE values are 9.0% and 10.8%, respectively; 100 minus WAPE must not be labelled accuracy. Booked hours are not confirmed delivered technician effort, and separate Calendar entries are not necessarily unique completed visits.

The forecasts start with surviving appointments entered and last updated before the forecast origin, then estimate later additions. All fitting labels mature before each origin. Model selection uses only validation labels ending and last updated before the first assessment origin, 6 July. The current surviving snapshot cannot recover deleted/moved appointments or earlier versions, and the later outcomes have already been inspected during broader project research. These remain promising research candidates, not proven live forecasts. No deployment was performed.

## Scope completed

- Return targets: 90 configurations across three targets, five model families, three input sets and two training histories. Nine fixed policies assessed. The authoritative corrected run reserves all assessment property/programme groups before any model selection.
- Monthly customer repurchase: 60 feasible configurations, 156 development fits, five supported population/horizon tasks; 180-day already-repeat-customer task was infeasible. Positive customer counts are much smaller than overlapping positive customer-month counts.
- Booking planning: 144 configurations attempted, 124 complete and 20 infeasible; four targets/horizons assessed against independently validation-selected strong simple baselines.
- Enquiries: five model families, 80 validation model/threshold comparisons; coherent current-release Sales/Prospects exports. Assessment has 1,021 contacts and 30 later sale matches. This is recorded-sale linkage, not a verified won/lost label.
- New official DOSM data: 2022 district household income, expenditure and poverty, plus two-month-lagged CPI and a date-only control. Five corrected paired fits, following five preserved invalid geography fits. Same larger 1,506 / 1,177 / 2,075 partition.

New household context raised precision from 23.02% to 24.63%, reducing false warnings by 46 but missing four additional returns. F1 and probability-quality evidence did not establish a dependable breakthrough. Trusted district coverage was 921 of 2,075 assessment services. Only 2022 HIES rows were used; the current CSV also contains 2024 rows. CPI publication dates preceded every prediction anchor. Current downloaded vintages may include revisions.

No new classifier qualified for promotion. The original frozen future test and production pointers are unchanged. No synthetic labels, late prospective predictions or favourable assessment-split selection were introduced.

## Corrections retained for audit

- `20261021_management_forecasts/`: initial selection included a few validation outcomes edited after assessment began. Marked DO_NOT_USE; corrected v2 is authoritative.
- `20261021_precision_targets/`: final model fits were group-purged, but earlier development was not globally purged of assessment groups. Marked DO_NOT_USE; corrected v2 is authoritative.
- Initial repurchase attempt: outcome-maturity flaw preserved and excluded; corrected historical run explicitly acknowledges adaptive reuse.
- Initial DOSM HIES fit: uncertain geocoding tiers were accepted. Marked DO_NOT_USE; `trusted_geography_v2/` checks exact geocode metadata and boundary uncertainty.

The model register excludes these invalid runs from its evidence index and explicitly recognises the separately verified nested DOSM correction.

## Verification and remaining limits

Saved classifier confusion matrices, probability metrics, source hashes and group/maturity splits were independently replayed. Forecast MAE, RMSE, WAPE, selected-baseline comparisons and validation-label maturity were recomputed. Separate agent review caught the forecast maturity issue and verified its correction. The historical return snapshot lacks per-row known-at metadata for every weather/source feature: date windows and hashes do not certify the exact vintage available at each past service. Notebook cells execute sequentially with valid notebook structure and zero error outputs; figures were inspected. Native Jupyter kernel execution was unavailable. The share pack omits private source rows, customer identities, model artifacts and credentials.

Next useful modelling evidence is a new live forecast comparison using complete saved Calendar snapshots. Current historical reconstruction is not sufficient to make live accuracy claims. Exact building age, dated building-level complaints, confirmed actual treatment duration, historical reschedule reasons and reliable payment settlement labels remain unavailable. The original future pest-return evaluation remains a separate experiment; this modelling turn did not audit its current collection state.
