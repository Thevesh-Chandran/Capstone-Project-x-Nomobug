# Assistant speed release — 16 October 2026

Revision cp2-portal-00029-rnr, 100% traffic. Build 67d58726-5124-420d-a304-a88491ffd855. Rollback cp2-portal-00027-jt4 (before this turn).

CPU Ollama service remains llama3.2:3b on 4 CPUs/8 GiB. No GPU, always-on minimum instance or IAM expansion introduced.

Changes: bounded per-instance answer cache (64 results/15 minutes), keyed by exact question, Malaysia date, complete snapshot/evaluation/registry, provider and model; successful validated answers only; defensive copies; source updates invalidate. Ollama requests specify 30-minute model retention, 220 generated tokens (previous350), 4096 context (previous8192), four threads. Unknown-topic requests send core evidence rather than all tables. Model retention does not prevent Cloud Run instance recycling.

Confirmed commercial and annual warranty FAQ phrasings use verified policy directly. Weekly payment question uses all reminder rows filtered to Malaysia Monday–Sunday, with no inference of nonpayment. Missing/unconnected source data is explicitly unavailable rather than zero.

Verification: 31 focused portal/storage tests passed, including cache source invalidation, failed-answer exclusion and weekly reminder date filtering. Cloud Build import smoke passed. Local policy/payment computation measured ~1–2 ms. Live weekly answer verified as 12–18 October (four aggregate date/arrangement rows representing five contract reminders). Initial cold startup surfaced missing reminders; final release adds the source-availability guard. Fresh generated-answer latency is not established by this release; a browser probe was still processing at the last check. No guarantee that all new questions answer instantly.
