# Metabase on Oracle Always Free

Status: deployment prepared; Oracle account sign-up and actual server capacity are pending. No Oracle resources have been created. Container startup has not been tested on Oracle.

## Server request

- Always Free account, no Pay As You Go upgrade.
- Home-region `VM.Standard.A1.Flex`, **2 OCPUs, 8 GB RAM**; only proceed if the Console explicitly confirms Always Free eligibility and no existing account usage exhausts that allowance.
- Always Free Ubuntu ARM64 image; 50 GB boot volume within the account's available free storage allowance.
- Do not substitute paid shapes, larger resources, paid databases or a load balancer when free capacity is unavailable.
- Restrict SSH ingress to the owner's IP. Do not expose port 3000 or 5432 publicly.

The official Metabase v0.65.2 image manifest contains linux/arm64. Its pinned multi-architecture digest is retained. The PostgreSQL 16 image is also official, pinned and ARM64-compatible. Registry evidence is in `outputs/metabase_trial/oracle/`. Manifest compatibility is not a successful runtime test.

Oracle currently documents 1,500 OCPU hours and 9,000 GB hours each month for A1 Always Free resources (equivalent to 2 OCPUs/12 GB). Allocations must be checked across the whole account, not per VM. Availability is not guaranteed, and idle instances may be reclaimed.

## Initial installation after account and VM checks

Use the official Docker installation instructions for the selected Ubuntu release. Copy only this deployment folder to the VM; never copy the entire project, customer data or local credentials. On the server:

```sh
python3 prepare_server.py
docker compose config --quiet
docker compose up -d
docker compose ps
curl --fail http://127.0.0.1:3000/api/health
```

The setup creates unique server-local database, encryption and session secrets without printing them. It refuses to overwrite existing secrets. Both settings and plugin volumes persist across container recreation. The database runs on the same free VM; the earlier Neon trial is left untouched.

Initial browser access is through an SSH tunnel, for example `ssh -L 3000:127.0.0.1:3000 ubuntu@SERVER_IP`, then `http://127.0.0.1:3000`. The server keeps running when the laptop is off. The user must create the Metabase administrator password themselves. No customer data or BigQuery connection is needed for the first health test.

Before offering a public management link, configure and verify HTTPS and authenticated access. Do not expose this initial HTTP port directly, bypass certificate warnings, or enable public sharing as a workaround. Hostname/TLS and actual MCP connectivity remain later acceptance steps.

## Acceptance

1. Console confirms eligible shape, disk, region, account totals and billing plan.
2. Metabase and database both become healthy; memory use stays within the VM.
3. Administrator creates one disposable chart/dashboard; restart/recreation retains it.
4. Save a PostgreSQL backup plus stable encryption/session secrets to a separate protected destination. Test restoration into an isolated database. Never use `docker compose down -v` during routine updates.
5. Complete/review MCP source security checks and verify authenticated create/edit/readback on disposable content. Existing static scanning was incomplete; do not describe the MCP implementation as certified or connected.
6. Only then add read-only approved BigQuery views and reconcile actual dashboard totals. No raw contact/address exports.

Source: https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm

Docker deployment: https://www.metabase.com/docs/latest/installation-and-operation/running-metabase-on-docker
