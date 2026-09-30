# Nomobug CP2: recorded callback risk

Start with [the model guide](planning/CP2_START_HERE.md). It explains the prediction, current evidence and which files to use. [Project status](planning/PROJECT_STATUS.md) holds the detailed implementation history.

The main experimental model ranks paid services by the risk of a recorded corrective Calendar callback within the following 30 days. It produces a numerical risk score for a binary outcome. Warranty entitlement is calculated separately from the owner's policy.

The current experimental candidate is **corrected v5 ExtraTrees, depth 10**. On 100 newer services it found four of five callback-positive windows within 20 reviews, versus three for the corrected reference. Five positives are too few to establish a dependable improvement. [Current model evidence](planning/CP2_CORRECTED_MODEL_CANDIDATES_V5.md) explains the selection, corrections and limits.

The future-test refit trains on all 5,695 mature services, including 2,075 from 2026. Use `scripts/cp2_model.py status` or `verify` for the current model. A private Cloud Run collector now checks every two minutes for the frozen prospective experiment; a separate Cloud Run job publishes reconciled reporting views daily at 06:00 MYT. No future accuracy has been measured: the earlier cohorts missed service windows, and first-service detection remains weak. A new cloud cohort starts 1 October. The owner is finishing the management dashboard. [October submission status](planning/CP2_OCTOBER_SUBMISSION.md) tracks what has passed and what remains.

## Find the right files

| Folder | Use |
|---|---|
| [planning/](planning/README.md) | Current model guide, policy, evidence and next steps |
| [planning/archive/](planning/archive/README.md) | Completed evaluations and historical setup notes |
| [config/](config/README.md) | Model contracts, experiment provenance and source dictionaries |
| [scripts/](scripts/README.md) | Repeatable extraction, warehouse, analysis and model commands |
| dbt/ | Tested warehouse transformations and source lineage |
| tests/ | Synthetic regression checks |
| templates/ | Blank structured recording templates |
| notebooks/ | Introductory profiling notebooks |
| outputs/ and tmp/ | Private generated model artifacts, source snapshots and working files; ignored by Git |
| data/, docs/ and secrets/ | Private local data, preserved CP1 documents and credentials; ignored by Git |

Run commands from the repository root using `.venv/Scripts/python.exe`. BigQuery is the primary warehouse; `scripts/neon/` is a preserved manual fallback and `scripts/prototypes/` contains older exploration. See [the script inventory](scripts/README.md) before running a command.

## Data handling

Keep raw exports, customer details, Calendar descriptions, credentials and generated private predictions outside version control. Use synthetic or anonymized test data. Frozen experiment inputs and saved models are retained for reproducibility; their local outputs are not duplicate source records to merge into a dataset.
