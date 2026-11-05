# CP2 portal handoff — 14 October 2026

## Current deployed checkpoint (supersedes historical entries below)

Portal revision `cp2-portal-00012-kmm` is deployed privately at https://cp2-portal-964813222593.asia-southeast1.run.app. Google IAP sign-in and staff access were verified; the older deferred-sign-in notes below are superseded. Ollama remains private and invoked by the portal identity. Broad generated-answer quality and latency acceptance remains pending.

Reporting execution `cp2-reporting-daily-2n8ql` published release `20261014045314a561c6` with its approved private portal export. The reporting job was subsequently updated to image `860e1ace-cbd7-4ba0-b239-11ed549207e6`; that final image has not been independently rerun. Prior completed checks: 535 Python checks, 221 dbt steps and container smoke verification. Do not interpret historical unfinished deployment lists as current blockers.

The website uses actual business geography/customer data separately from the 100-service historical model test. Highest-sales responses use verified deterministic figures, explicitly labelled; they are not evidence that all Ollama answers are reliable. Customer details remain private. Model weights, protocols and immutable prediction receipts are unchanged.

Current unresolved work is listed in [the submission checkpoint](CP2_OCTOBER_SUBMISSION.md): dashboard rendered acceptance is blocked by the controlled browser displaying blank report content; broader AI acceptance, current costs/collection coverage and final write-up still need verification. Future evaluation remains conditional and no earlier than 30 November.

## Historical implementation log

## Interface redesign

User requested a simple black-and-white Nomobug shell, with chart/dashboard colours independent of the shell, and explanatory text behind information icons. Inspected https://component-library-rho.vercel.app/pages/app-shell visually. Implemented own HTML/CSS/SVG (no component-library code or dependencies imported): local Instrument Sans with official OFL license, compact icon sidebar, restrained row-based workspace, short page titles, monochrome controls, a blue geographic map, conditional Sources pane and concise provenance labels. Supporting details are accessible through hover/focus/click information buttons, dismissible with Escape. Critical stale-data and zero-positive/small-evidence indicators remain visible. No background animations or decorative motion.

Local Chrome verification covered assistant empty/answer/source states, information popover opening and Escape dismissal, area explorer, workspace and system status. JavaScript syntax, public font MIME/magic and 12 portal tests pass. Build 236c44df-ae8c-440f-904e-51f267249ef4 succeeded; deployment verification pending. Looker report definitions, model and collector unchanged.

Redesign deployed successfully as cp2-portal-00009-tb7, 100% traffic. Verified the live monochrome assistant, connected Ollama status, preserved staff session, and tooltip open/Escape dismissal in Chrome. Live proofs: outputs/portal/proof/monochrome_assistant_live.png and monochrome_help_live.png. Temporary local design preview is stopped after review. The earlier source freshness and broader AI acceptance items remain outstanding; cosmetic changes do not resolve them.

## Google sign-in completed

User created and downloaded dedicated CP2 Portal IAP Sign-in web OAuth client. Added Google's documented IAP handleRedirect URI and applied its credentials to project IAP OAuth settings, preserving the prior settings in ignored secrets/iap_settings_before.json. Current credentials are in ignored secrets/iap_settings.json; never print or commit them. Existing Sheets/Calendar OAuth client was not modified. Initial unsaved AI-agent classification change was cancelled; saved client remains ordinary web sign-in.

Verified through Chrome: Google account selection and email-only consent reach the deployed portal; staff access login succeeds; approved private GCS data and DOSM boundary map load; hosted radius endpoint returns 8 services and 7 uncertain exclusions for the default 10 km area. Anonymous portal API redirects to Google sign-in (302); anonymous Ollama access is forbidden (403). Website remains private to the owner's IAP access list. Hosted Ollama reports connected. Real browser model-question response is being checked; do not assume general answer quality from connection status.

Freshness remains a separate issue: visible source snapshot is 12 October and the website displays its stale-data warning. Optional reporting-to-portal export hook still needs deployment and recovery verification.

The first real hosted model answer incorrectly claimed the known baseline and sample were missing; the attached evidence proved they were present. Fixed with plain-English historical facts plus fail-closed comparison/sample guards. 10 portal tests pass, including regression rejection of that exact error. Real Ollama test returned 94%, 95%, 100 services and 5 cases with historical_model citation in 43 seconds; receipt outputs/portal/ollama_model_guarded_smoke.json. Build 96f3bf0a-6908-44d0-bcec-fdf00b89fdb4 succeeded; deployment update underway. The guard targets observed overall-metric errors and is not a guarantee of all generated reasoning.

Build 96f3bf0a deployed successfully as cp2-portal-00006-568. Fresh deployment verification exposed two runtime issues, fixed locally with regression tests: cookie signing must survive instance restarts (derived from the existing high-entropy staff secret; rotation invalidates sessions), and the first GCS pull must run immediately even when container monotonic uptime is under 300 seconds. 12 portal tests pass. Build 0daa37b4-ffcc-4037-9cae-f35ab7fa5ef4 contains both fixes; final deployment/check pending below.

Build 0daa37b4 deployed as cp2-portal-00007-tmq. A subsequent browser AI answer contained all numerical figures but falsely claimed the baseline used a different sample. Final approach supersedes the fragile generated comparison guard: standard overall accuracy/reliability questions return the verified historical facts directly, explicitly labelled as non-AI evidence. Broader questions still use Ollama. This avoids generation entirely for the core comparison and preserves the true same-sample denominator. Regression test asserts the comparison route never calls the generation transport. All 12 portal tests pass. Build f77451d1-bf5e-453e-9414-6fda583a79bf is the candidate for this final change; inspect deployment result before claiming current.

Final candidate deployed successfully: f77451d1-bf5e-453e-9414-6fda583a79bf -> cp2-portal-00008-68g, 100% traffic. Full Python suite: 526 passed, 19 existing rasterio warnings, 31.53 seconds. Website URL: https://cp2-portal-964813222593.asia-southeast1.run.app . Owner-only Google IAP policy rechecked. Initial Google setup is complete; broader generated-answer quality, fresh reporting export and recovery checks remain separate outstanding items.

## Resume update — scope correction

The user clarified that website features must complement Looker, not duplicate it. Removed native sales charts, KPI cards, payment reporting, static model-results page and repeated source-quality table. Five website sections remain: workspace entry, embedded Looker dashboard, interactive district/radius evaluation, Ollama assistant and runtime status. Approved business aggregates remain private assistant evidence.

Portal checks pass (8 tests), JavaScript syntax passes and the simplified workspace was verified in Chrome. Design proof: outputs/portal/proof/streamlined_workspace.png.

Cloud Run cp2-ollama is private and ready; model llama3.2:3b is present. Only cp2-portal-runtime has service invocation access. Cloud Run cp2-portal is deployed privately with GCS reads and service identity authentication to Ollama. Browser IAP lacks the initial OAuth client setup; the user explicitly deferred that setup. Do not make the portal public as a workaround.

Current deployed portal image is 409abf4a-53d4-49f6-83db-feb7cddf4fc1, containing the corrected five-section interface. Build db7340de-d322-4602-8a88-6288c3bde15e succeeded with structured AI output; this is not yet the latest local prompt revision. Initial real inference was rejected for invalid evidence references. Schema-constrained inference returned valid references but a contradictory yes/no warranty answer, so the local prompt now explicitly requires Yes with the 30-day condition and deduplicates references. Recheck before calling AI ready. No model weights or collector changes.

Earlier completion/pending lists below describe the previous night's checkpoint; this update supersedes conflicting deployment and website-scope statements.

Final local verification: 522 Python tests passed, 19 existing rasterio warnings. Bounded structured-output AI revision returned the correct conditional Yes answer for rescheduled residential 3x warranty with warranty_policy reference (16 seconds). Broader AI reliability remains to be checked. Final website build a7b0540d-c17b-4dc7-84c0-5c9cce5a07cf succeeded and deployed successfully as cp2-portal-00003-t68, with 100% traffic. IAM rechecked: portal allows only the IAP service agent; Ollama allows only portal runtime. Google IAP setup stays deferred; do not claim the hosted browser flow is ready.

AI performance follow-up: the all-evidence model question hit the 180-second timeout. Added deterministic relevant-evidence selection: model questions omit payment/reminder rows, and district/radius evidence is included only for geographic questions. Unknown questions retain the full approved evidence set. Added a regression guard for relevant evidence, bounded source references and deduplication; 9 portal tests pass. Build 10fa9785-c55b-44f0-9dfd-af4d885237b7 succeeded; deployment update started. Broad AI latency/quality acceptance is still pending; a warranty-policy smoke test alone does not establish it.

Deployment 10fa9785 completed: cp2-portal-00004-z56 serves 100% of traffic. The earlier test (before the last, tighter geographic evidence filter) returned a correctly cautious model answer with valid sources in 107 seconds, but omitted the requested numerical baseline comparison. Saved as outputs/portal/ollama_model_smoke.json. This is a material AI answer-quality/latency limitation, not complete acceptance. Latest retrieval filter has unit coverage; verify real latency and complete baseline response next. No source records, dashboard definitions, frozen model or prospective collector were modified.

Paused at the user's request for the night. Temporary local preview and local Ollama image pull stopped. Existing cloud prospective collector was not changed.

## Completed

- Python website with overview, embedded Looker report, district/radius explorer, historical model results, payment reminders, AI interface and system status.
- Original historical artifact hash checked and predictions replayed; no training, threshold changes or retrospective prospective predictions.
- Official DOSM boundaries with conservative location uncertainty handling. Only 49 of 100 held-out services can be reliably assigned to districts; small samples remain limitations.
- Actual approved Gold data refresh passed. Source snapshot is 12 October, explicitly shown as stale when appropriate.
- Full Python suite passed: 522 tests (before latest storage/export additions). Latest portal and reporting release checks: 17 passed after those additions. JavaScript syntax and browser flows checked.
- Local website Docker image built. Cloud Build 784c80ce-cc03-4cd7-bcb0-176fc737c1f8 in asia-southeast1 completed SUCCESS, producing portal and Ollama images in the existing cp2-reporting Artifact Registry repository.
- Private bucket gs://cp2-portal-profound-keel-500007-s4/current contains four portal data files. Separate portal and Ollama runtime service accounts created. Portal access code stored in Secret Manager; no secret values recorded here.

## Not finished — resume here

1. Review and test webapp/storage.py and optional reporting export failure handling. Ensure audit failure cannot incorrectly mark an already published Gold release as failed.
2. Rebuild the website with cloudbuild.portal-web.yaml: the successful initial cloud build used a staged website source BEFORE the latest GCS and authenticated Ollama additions.
3. Deploy private Ollama and portal Cloud Run services with scoped service-to-service invocation. No new portal or Ollama Cloud Run service has been deployed yet.
4. Confirm browser authentication and actual project-specific spending before exposing the website. Account-wide billing showed usage offset by credits; that is not verified project-specific cost.
5. Test real Ollama inference, answer evidence, latency and failure handling. AI interface is wired, but real answers have not been verified.
6. Rebuild and update the reporting job to export approved aggregates after successful publication. The optional code hook exists; the active job has not been updated.
7. Verify cloud end-to-end flows, privacy, last-good recovery and update the runbook with actual deployed URLs.

Do not blindly rerun infra/setup_portal.ps1 -Apply: its create operations already succeeded and are not idempotent.

Private local access files are under ignored secrets/; never print, commit or put them in container images. Private area rows under outputs/portal must not be served to browsers.

The model remains experimental: held-out 100 services, five pest-related returns, four found in the original top 20; accuracy 94% versus 95% always-no-return baseline. District filters do not establish a better model. Future collection and the governed 30 November evaluation remain separate and unchanged.
