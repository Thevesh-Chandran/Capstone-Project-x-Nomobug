> **Resolved — 21 October 2026:** Google now shows **In production**. The same read-only connection was renewed afterward, Secret Manager token version 5 installed, refresh exchange and both approved Sheets metadata checks passed, and cloud source/model check `cp2-planning-weekly-gvqkf` succeeded. Earlier Testing/pending notes below describe the previous state. Evidence: `outputs/oauth_publication/20261021/production_verified.json`. Model weights and workspace permissions were unchanged.

# Website access — Google sign-in only

**5 November 2026, 20:24 MYT:** revision `cp2-portal-design-1105c` (Cloud Build `89dc93a2-87e6-4f53-8c4b-d2d96a350b01`, smoke passed) serves 100% of traffic. Image-only update: IAP, `CP2_AUTH_MODE`, data, action-ledger and calendar settings unchanged. Traffic had been pinned to `cp2-portal-design-1105b`, so it was moved explicitly; the planning, reporting and design-preview tags are kept. Includes the management overview and booking changes, the retired AI assistant, readable page addresses (old ones still work), the overview wording and loading fixes. 770 Python tests passed. Browser check through Google sign-in still to do by the owner. The check-in pilot stays off until `CP2_CHECKIN_PILOT_APPROVED=yes` is set after owner agreement.


## 2 November dashboard release

The custom dashboard entry is https://cp2-dashboard-thevesh20-3384s-projects.vercel.app/ and redirects to the existing protected Cloud Run `/reports` page. Revision `cp2-portal-00087-cep` serves normal traffic. IAP and its existing audience remain enabled. Vercel hosts public interface files only; data stays on the protected backend. All 761 Python checks passed; all four report pages and anonymous sign-in redirects were verified. The last approved source is still dated 28 October and is visibly marked stale. See [hosting records](../infra/CP2_DASHBOARD_HOSTING.md).

The hosted portal uses Cloud Run IAP and verifies the signed `X-Goog-IAP-JWT-Assertion` on every private API request. The extra staff access code is no longer required in IAP mode. Google sign-in and its authorized-viewer list remain in place; the website is not public.

Deployment requires `CP2_AUTH_MODE=iap` and `CP2_IAP_AUDIENCE=/projects/964813222593/locations/asia-southeast1/services/cp2-portal`. Google signature, expiry, audience, issuer and subject checks fail closed. Public certificate responses are cached; user assertions are not cached. The default local/staff-code mode remains available for local development and rollback.

Before enabling this mode, verify `run.googleapis.com/iap-enabled=true` and that only the IAP service identity has `roles/run.invoker`. Do not disable IAP or add public invokers to avoid sign-in. The staff cookie is ignored in IAP mode, including after its eight-hour expiry.

Validation: 659 Python tests passed on 21 October 2026, including invalid/missing assertions, wrong issuer, missing audience and staff-cookie rejection in IAP mode. Live release verification is recorded in `outputs/planning_rollout/20261021/`.

## 21 October source repair

Reporting run `202610211016248abea7` stopped before publication because the programme-stage invariant returned two failures. Its restricted candidate Calendar snapshot matches the same reviewed event identity hash `22fbea10b355df2b759c2a09b4ffe833fcc572ac8f79dea65927c9f76f33dbb9`, same matched sale CUST981, stage 13/24, non-warranty service, now on 18 October rather than 11 October. Updated only that expected reporting date in `dbt/seeds/paid_programme_visit_overrides.csv`. Existing ownership confirmation of the 4+20 service programme remains unchanged. No blanket Sunday rule or relaxed identity/stage check was introduced.

Recovered the original immutable release manifest from the restricted audit row and resumed the same candidate snapshots locally. This recovery does not reconstruct or backfill model predictions. A corrected reporting container is being prepared for future scheduled runs. The original failed cloud execution remains in its audit history.

Cloud Build source uploads now use the same explicit allowlist as Docker (`.gcloudignore`). This fixes a deployment packaging error: the default Git-derived ignore rules omitted the approved public DOSM district boundary file required by the reporting image. Customer exports, source credentials and private caches remain excluded. Use `cloudbuild.web.yaml` for website-only changes so the unrelated Ollama image is not rebuilt.

## Verified completion

Website revision `cp2-portal-00049-6mv` serves 100% of traffic. The extra password secret mapping is removed. Google IAP remains enabled, and the application verifies its signed headers. The real Google invalid-signature test was rejected. Normal browser access succeeds without a staff cookie; `Switch Google account` uses Google's documented IAP cookie-clear flow.

Reporting recovery `202610211016248abea7` completed: dbt **222/222 passed**, all 16 independent KPI checks passed (`pass_with_business_caveats`), **53 views published**, and portal export `PUBLISHED`. The live freshness warning cleared. Reporting image `release:ac089c74-7862-4ee2-bf8f-8414b6ea04c7` is installed for future scheduled runs. The failed initial cloud run is preserved, followed by the explicitly resumed recovery in the release audit. A natural scheduled execution of the new image has not yet occurred.

Final Python suite: **659 passed** (20 existing rasterio deprecation warnings). Original frozen bundle SHA-256 is unchanged. Live browser console errors: none. Final screenshot: `outputs/planning_rollout/20261021/google_only_access.png`.

Still pending: owner's OAuth Branding/publishing setup and subsequent read-only credential renewal, as documented in the planning operations guide. Location coverage remains incomplete; unknown or ambiguous locations are not invented. Future model evaluation still requires actual future outcomes.
