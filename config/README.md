# CP2 configuration map

Use [the model guide](../planning/CP2_START_HERE.md) to choose the active model. A higher file version or more variables does not by itself establish better predictive performance.

| Contract | Role |
|---|---|
| `cp2_model_current.json` | One current corrected v5 model pointer |
| `warranty_model_experiment_v5.json` | Fixed candidate selection on corrected development data |
| `warranty_new_holdout_v5.json` | One final newer-date evaluation |
| `warranty_prospective_experiment_v2.json` | Corrected refit using all mature data |
| `warranty_model_experiment_v4.json` | Historical reviewed reference; superseded as current candidate |
| `warranty_blind_spot_experiment_v1.json` | Historical focused RandomForest experiment; superseded as current candidate |
| `warranty_prospective_experiment_v1.json` | Historical pre-correction frozen bundle; superseded by v2 |
| `callback_date_authority_review_v1.json` | Owner-resolved, snapshot-scoped Calendar date authority for seven cases |

The current primary is `et10_leaf5`, selected from purged development evidence before the newer holdout was accessed. [The corrected v5 report](../planning/CP2_CORRECTED_MODEL_CANDIDATES_V5.md) explains the model, later-date test and fixed future comparison. `cp2_model_current.json` identifies the exact private bundle and hash; use `scripts/cp2_model.py` to follow it.

The earlier `warranty_risk_model_v1.json`, `v2.json`, `v3.json` and `warranty_coverage_episode_model_v1.json` are historical contracts. Regression tests and reproduction code still read them at these paths; they are not active replacement recommendations. The flood, 2026 training, callback-error and description experiment configs preserve completed comparisons and source hashes. Their reports are under [the evaluation archive](../planning/archive/README.md).

The CSV dictionaries, inventories and mapping decisions describe source structure and quality. They are not training inputs to concatenate. `google_source_ids.example.json` is an example only; real approved source IDs and credentials stay in ignored `secrets/`.
