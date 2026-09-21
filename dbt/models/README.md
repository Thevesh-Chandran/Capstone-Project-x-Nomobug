# Nomobug transformations

`prospects_2026.sql` creates a Silver view over one verified immutable snapshot.
The refresh runner passes its identity and timestamp together as required dbt
variables. There is no hard-coded September 3 fallback.

All raw columns, row positions and placeholders remain available. Derived fields
do not replace the originals. Follow-up dates stay raw until year rollover is
verified. Acquisition grouping now separates campaign codes, named channels,
unknown (NA), missing and unresolved labels. Phone normalization is still pending;
BEDBUGS remains flagged pending confirmation of its proposed mapping.

Build and run the tests from the repository root:

```powershell
python scripts/refresh_prospects_2026.py --refresh
```

The initial profile targets the existing Singapore silver dataset.
The 100 MiB per-query setting limits query bytes, not total cloud spending.

The runner builds the full current dbt project, including the independent
mapping test, then prints the aggregate checkpoint. See planning/PROSPECTS_REFRESH.md
for failure semantics and remaining production-hardening work.
