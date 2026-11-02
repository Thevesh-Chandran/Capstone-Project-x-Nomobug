# Metabase demo

Vercel Hobby project: cp2-metabase-demo (prj_IyeXBHpDpPEetaCkadhnOWF5BfpX).
Team: thevesh20-3384s-projects.

Official Metabase v0.65.2 is pinned by digest. This package refuses to start without persistent PostgreSQL. No data or credentials are copied into the image. Existing CRM projects, Cloud Run services and the Looker report are separate.

Connect a free Neon database in Vercel Storage. Configure these environment variables directly in Vercel:

- MB_DB_CONNECTION_URI: PostgreSQL JDBC URI with sslmode=require.
- MB_DB_USER and MB_DB_PASS: database credentials.
- MB_ENCRYPTION_SECRET_KEY: a stable generated random secret, preserved across deployments.
- MB_SITE_URL: the deployment URL.
- PORT: 3000.

Neon's DATABASE_URL alone does not configure Metabase. Do not commit actual values or paste them into chat.

Acceptance requires a healthy container, admin setup, read-only BigQuery connection, reconciled Overview totals, restart/redeployment persistence, authenticated MCP connectivity and free-tier usage checks. Default Vercel deployment protection has not been relaxed. Do not expose customer records to fix OAuth connectivity.

Neon connection is verified through the Vercel UI. start.sh automatically consumes PGHOST_UNPOOLED (or PGHOST), PGDATABASE, PGUSER and PGPASSWORD without reading their values into chat or source files.

The first deployment built but failed the Vercel 28-second startup deadline. The replacement uses a small local HTTP proxy to accept connections immediately and wait up to 240 seconds for Metabase's /api/health. /cp2-health returns 503 until Metabase is healthy. Writes are forwarded once only, and response cookies are preserved. Two local integration tests cover forwarding and truthful health status. This is still a compatibility trial, not accepted hosting.

Current status (2 November 2026): application startup remains BLOCKED. Latest deployment dpl_9RRwSkCZKRTGZoYug7b39nb1tLTW builds, but the real root request returns HTTP 500 FUNCTION_INVOCATION_FAILED during migration-resource loading. Health, admin setup, persistence, BigQuery and MCP acceptance have not passed.

The diagnostic deployment dpl_AGATpvmMU3je4cxJWjSNA66kRmuT explicitly logged JVM fatal OutOfMemory encountered: Metaspace with a 256 MiB Metaspace limit (exit -6). The correction allocates 512 MiB Metaspace and 384 MiB heap, with serial GC and one active processor. That removed the observed Metaspace error but did not produce readiness. The last corrected resource sample shows 2,143,580,160 bytes used against a 2,147,483,648-byte container limit, and JVM RSS 878,424 KiB. Its last sampled OOM-kill counter is zero. Near-limit memory is evidence of pressure, not proof of the final termination mechanism. No further identical deployments are warranted without new diagnostics.

The proxy logs only allowlisted resource counters, child exit status and termination signals. It never dumps environment values, command lines, credentials or request bodies. Both local forwarding/health tests pass. Diagnostics do not establish real Metabase readiness.

Database inspection earlier found no other active sessions or advisory locks and 104 migration records. No lock was force-released. MB_ENCRYPTION_SECRET_KEY and MB_SESSION_SECRET_KEY remain to be configured before acceptance; connector environment read/write calls and the trace API return 403 and no authenticated CLI fallback is installed. Do not retry unchanged or expose credentials to bypass this.

No customer data was imported, no paid upgrade was made, and existing CP2 services/Looker are unchanged. Deployment protection remains enabled. The next architecture decision is whether to use a lightweight Vercel frontend with the existing protected backend, or a separately approved persistent Metabase host. Neither alternative has been deployed by this trial.

Source review is recorded under outputs/metabase_trial/source_review. The static scanner did not complete; the bounded trial uses the documented manual-review fallback with CAUTION and no customer data.
