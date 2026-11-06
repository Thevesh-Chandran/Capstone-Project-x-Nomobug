# Business dashboard frontend

Entry: https://cp2-dashboard-thevesh20-3384s-projects.vercel.app/

Vercel Hobby serves only `dashboard.js`, `dashboard.css`, the entry page and routing configuration. There are no credentials, customer records, database connections, model binaries or server functions in this deployment. The entry redirects to the protected Cloud Run `/reports` page.

Cloud Run serves the small HTML document and `/api/reporting` after its existing Google IAP checks. Scripts execute in that protected page and fetch data from the same origin. This avoids third-party authentication cookies, API proxies, public data exports or a second sign-in system. Static code is public; reporting data is not.

The page has Overview, Sales, Visits and Payments. Month, district and named-pest filters apply to the first three. Payments uses current tracker records and explicitly ignores those filters. Linked customer contract status has narrower coverage than the full tracker summary; the captions distinguish them. The data refresh uses the existing approved snapshot pipeline; deploying frontend code does not refresh it.

## Updating

1. Edit the JS/CSS here. Keep all data access relative to `/api/reporting`; never add secrets, customer fixtures or source exports.
2. Update each version query and SHA-384 integrity attribute in `webapp/static/reports.html` from the exact asset bytes. Versioned URLs prevent stale browser assets from failing the integrity check during releases.
3. Deploy these four allowlisted files to Vercel project `cp2-dashboard` (team `thevesh20-3384s-projects`). No dependency installation or container is needed.
4. Verify unauthenticated JS/CSS responses, CORS headers and byte hashes. Run `tests/test_reporting_dashboard.py` and the portal/IAP checks.
5. Build the backend with `deploy/cloudbuild.portal-web.yaml`, stage a revision with no traffic, and check all report pages before promotion. Preserve IAP, runtime identity, environment and the previous revision.

Only the exact Vercel asset origin is allowed by the backend CSP. Changing its hostname requires an explicit allowlist change; arbitrary origins are rejected. The Metabase experiment is separate and is not required.
