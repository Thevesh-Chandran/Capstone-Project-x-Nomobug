# New evidence for future model improvements

Read [the recording guide](../planning/CP2_CALLBACK_RECORDING_GUIDE.md) before filling these files. Templates are blank; no customer data belongs in Git.

| Template | Use |
|---|---|
| `cp2_service_observations_v1.csv` | Inspection evidence, actual treatment and access details; one versioned history per paid service |
| `cp2_callback_outcomes_v1.csv` | Return request, visit reason, scheduling and completion evidence; one versioned history per return case |
| `cp2_prediction_anchors_v1.csv` | Validated service linkage and prediction timestamps from private source exports |
| `cp2_callback_recording.csv` | Older combined reference; use the separated v1 templates for the implemented validator |

Save filled copies under ignored `outputs/`. Run `python -m scripts.prepare_service_observation_features --help` from the repository root with the project virtual environment. It prepares candidate data only; it does not connect new fields to the cloud collector, change labels or retrain the frozen model.
