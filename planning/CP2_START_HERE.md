# CP2: current model

Start with **corrected v5 ExtraTrees, depth 10**. [Full results](CP2_CORRECTED_MODEL_CANDIDATES_V5.md) and [current model pointer](../config/cp2_model_current.json).

The question is: **will a recorded corrective Calendar callback occur within 30 days after this paid service?** The target is binary; the output is a numerical risk probability. It measures recorded callback work. Warranty entitlement is separate and follows [your confirmed rules](WARRANTY_POLICY_RULES.md).

The model uses service/package stage, prior callback history, normalized pests and premise type, past weather, waterway proximity and local environment. Future-created history is excluded. A warranty-eligibility feature was also tested in a secondary candidate; it never forces commercial callback probability to zero.

## Performance to understand

On 100 newer services with five positive callback windows, reviewing the highest-risk 20 found **four positives**, compared with three for the corrected reference. AUC was **0.891 versus 0.813**. Five positives are too few to establish a dependable win.

On the larger, previously inspected 2026 diagnostic, v5 found 103 of 179 positives in 395 reviews; the corrected reference found 97. First-service detection remains weak: zero of eleven at that review budget. See the full report for precision, AP and uncertainty.

The final future-test refit uses **all 5,695 mature services, including 2,075 from 2026**. Its training scores are not accuracy evidence. A private Cloud Run collector now reads Google sources, derives temporary BigQuery features and records time-stamped predictions; the owner's laptop can be off. The separate reporting release runs daily at 06:00 MYT. By 30 September 20:06 MYT, the collector had logged **seven real predictions** and retained **29 raw missed windows** across the original and repaired cohorts. The first 24 included six extra warranty visits; the next two were rescheduled service records whose old Calendar titles said `CANCELLED` but whose status remained confirmed. Three more windows were missed when a collector revision needed a Gold schema field that had not yet been published. The lookup and collector were repaired; scheduled ticks, a full source-to-model smoke, and a real service-end receipt **1.40 minutes** after its scheduled end passed. The old misses were not backfilled. The new 1–27 October cloud cohort was declared before its start and needs complete timely coverage before a future accuracy claim. Nine negative 2024–25 training rows retain this pre-correction title/status mismatch in the frozen bundle, a limitation of the historical result. Earlier address reuse reduced missing coordinates from 103 to **39** of 205 scored anchors and raised complete prior-30-day weather coverage from 102 to **166**. That is a feature-coverage gain, not measured accuracy. [Operations and future-test guide](CP2_LIVE_PIPELINE_OPERATIONS.md) and [October submission status](CP2_OCTOBER_SUBMISSION.md).

## Use one command

```powershell
.\.venv\Scripts\python.exe scripts\cp2_model.py status
.\.venv\Scripts\python.exe scripts\cp2_model.py verify
.\.venv\Scripts\python.exe scripts\cp2_pipeline.py status
```

The command also supports `predict`, `log-prospective` and `evaluate-prospective`. [Runnable commands](../scripts/README.md). The primary serialized model is `outputs/cp2-v2/prospective_callback_v2/challenger_all_history.joblib`; predictions and model binaries stay in ignored local outputs.

## Where to look

| Folder or file | Purpose |
|---|---|
| [This v5 report](CP2_CORRECTED_MODEL_CANDIDATES_V5.md) | Current model, corrections, evaluation and limits |
| [config/](../config/README.md) | Current pointer and reproducible experiment evidence |
| [scripts/](../scripts/README.md) | Current entry point and extraction/training tools |
| [Recording guide](CP2_CALLBACK_RECORDING_GUIDE.md) | Better future callback and treatment data |
| [Live pipeline operations](CP2_LIVE_PIPELINE_OPERATIONS.md) | Cloud collection, failure recovery, timed logging, and final outcome test |
| [Business KPI validation](CP2_BUSINESS_KPI_VALIDATION.md) | Source-backed checks and known KPI freshness gap |
| [archive/](archive/README.md) | Completed experiments and historical setup |
| [October submission record](CP2_OCTOBER_SUBMISSION.md) | Reporting architecture, acceptance status and dashboard handoff |

The current candidate supersedes the earlier v4 recommendation. Earlier contracts remain at stable paths where tests/replay still require them. Source data and owner reviews are preserved. [Detailed history](CP2_PROJECT_HISTORY.md).
