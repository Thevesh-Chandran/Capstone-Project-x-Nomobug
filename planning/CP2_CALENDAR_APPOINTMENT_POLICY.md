# Calendar cancellations and temporary appointments

Owner clarification recorded 4 October 2026: real Sunday services have occurred.
Sunday is never a rule for excluding an appointment. Colour, overlapping cancelled
entries, and the absence of a replacement date cannot be inferred from weekday.

A cancelled original appointment represents that slot being cancelled or
postponed. It does not cancel the sale, client, contract, or replacement event.
Cancelled entries remain in raw evidence and are excluded from service workload.

The owner confirmed one temporary Syimir second-service slot on 4 October,
3–4 pm Malaysia time. `dbt/seeds/calendar_appointment_overrides.csv` records its
hashed Calendar identity and exact start/end, without customer contact details.
Only that identity at that unchanged window is excluded as awaiting a client date.
Moving the event expires the exception automatically, including a move to Sunday.
Other Sunday appointments remain eligible under normal appointment rules.

Reporting and the collector use this same reviewed registry. Raw snapshots,
existing missed-window records, existing prediction logs, model weights, and the
frozen historical transformations remain unchanged.

## Verified release

Published reporting release `2026100404180522111f` updates 46 views. All 195 dbt
build/test steps and the independent KPI/privacy release gates passed. A read-only
warehouse check found exactly one reviewed placeholder, zero placeholders counted
as service, and 67 historical Sunday service entries preserved. The final Python
regression suite passed 466 tests.

Cloud collector revision `cp2-prospective-collector-00009-q4l` serves the correction;
a scheduled tick returned HTTP 200 at 12:24 Malaysia time. The daily reporting job
uses image digest `sha256:dd48c00d40c3640855e165d5d9e530903f1afa1fbb27973fc838a798a616edfc`.
The published release also includes the verified source-formula repairs and
aggregate recurring-reminder sources. This is operational validation, not evidence
of improved model accuracy or completion of the prospective experiment.
