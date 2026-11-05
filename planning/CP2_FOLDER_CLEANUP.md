# Project folder cleanup — 4 October 2026

Start with [the project guide](../START_HERE.md). It links the current dashboard
guide, model explanation, results, test dates and private reminder tracker.

Removed 14 disposable folders containing 37,191 files
and 1,725.4 MiB of generated content: test caches, scratch environments,
debug outputs and copied deployment build contexts. The deployed cloud images
and services are unaffected. Archived six superseded payment-tracker previews
under `outputs/recurring_payment_tracker/archive/`; their historical document
references now point to that location.

Added folder indexes for outputs, dashboard designs and recurring payments.
Updated introductory guides to the separately declared 5 October future test.
Runtime file names and fixed experiment paths remain stable.

Preserved source snapshots, credentials, the active environment, frozen models,
all prediction receipts, missed-window evidence, reporting releases, compiled
feature queries, private cloud artifacts and original CP1 documents. Older
experiment outputs remain because they support reproducibility, not because
they are current recommendations.

Verification: navigation links resolve, all frozen bundle/protocol and compiled
feature hashes are unchanged, and model replay reproduces all 5,695 rows with
maximum score difference below 3.4e-16. Cleanup changed documentation and
disposable local files; it did not retrain or deploy a model. Detailed manifests:
`outputs/project_audit/20261004/folder_cleanup_manifest.json` and
`outputs/project_audit/20261004/folder_cleanup_verification.json`.
