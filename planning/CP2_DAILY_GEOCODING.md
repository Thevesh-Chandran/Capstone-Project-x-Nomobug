# Daily address mapping

The existing cp2-reporting-daily Cloud Run Job runs at 06:00 Asia/Kuala_Lumpur. Geocoding now runs after immutable fresh Bronze snapshots are loaded and before candidate dbt builds, tests and KPI reconciliation. Its API key is provided by the cp2-geoapify-key Secret Manager secret to the reporting identity only.

The old release reused coordinates only for identical Calendar event identity and unchanged title/location/description. It made no new Geoapify requests. A fresh address or changed description could therefore lose coverage. Sales mapping also depended on an exact address match in Calendar geocodes.

The new stage reuses the historical validated cache, then requests up to 100 uncached or retry-eligible distinct sanitised addresses per run. The stage stops issuing requests after 240 seconds; the job remains one task, 20 minutes, zero automatic retries. Names, phones, emails and descriptions are removed before provider requests. Customer source records and API keys are not put in the container or logs.

Quality.geocoding_address_cache is an append-only durable cache of hashes, validated coordinates, precision/status and timestamps. It stores no input addresses or provider-formatted addresses. Temporary failures retry after increasing delays; authentication/quota failures stop the batch. Unchanged ambiguous or no-result addresses remain review items rather than being charged for every day. A changed address has a new hash. Verified manual matches stay protected.

Accepted Calendar coordinates are materialised as an immutable sidecar for that exact fresh snapshot. Existing event-coordinate rows are preserved. Sales may use a directly validated Sales address when no Calendar hash match exists. Sales coordinates never flow backwards into service visits. Strict map-precision rules and Malaysia bounds remain intact; coarse/uncertain matches can remain unmapped.

A per-run geocoding receipt is stored in the release manifest and durable audit. A provider problem is recorded as DEGRADED; valid previous mappings remain available. Ordinary reporting can still publish after its own checks pass. A failed candidate build/reconciliation never replaces the published Gold views. Cache results may survive a failed reporting release and be reused by a later run.

Daily requests do not guarantee all addresses will map. Pending batch work, missing/unusable address text, ambiguous provider results, conflicting matches and district-boundary uncertainty are separate limitations. The frozen model bundle and all existing prospective predictions remain unchanged.

17 October follow-up: dedicated Sales address fields now use explicit-field sanitisation, so named buildings and unit-led addresses are not rejected merely for lacking a conventional street prefix. Contact and secret tails remain stripped. Reads retain earlier valid address-cache keys and prioritise protected manual matches. The reporting image was rebuilt with container smoke checks and deployed by immutable digest; the daily schedule, identity and task limits are unchanged.

The owner-requested 2026 purchase review was processed with ordinary lookups, trusted-address comparison, richer provider reranking and transient locality hints. No Google coordinates or raw responses were stored. Reconciled website mapping increased from 660/886 to 759/886 purchases; 127 remain unlocated after the automatic work. These are purchases, not 127 distinct customers. Receipts and the refreshed private review are under `outputs/address_review/20261017_after/`. The website's runtime pulls private cloud snapshots at most every five minutes. Sales totals were reconciled before publication; model files and historical predictions were not changed.
