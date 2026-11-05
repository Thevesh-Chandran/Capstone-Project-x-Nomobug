# Workspace design release — 16 October 2026

Deployed revision: cp2-portal-00026-bgw (100% traffic).
Build: 7220610c-5a9e-4c40-8582-e2e986b1e07a.
Previous revision: cp2-portal-00025-j2x.

Replaced mixed top navigation styling with a consistent fixed sidebar, neutral application surfaces, restrained tool colours, aligned typography, divided metric strips and clearer tables. The standalone map shares the same navigation and visual language. Overview is now the default landing page. No data calculations, model settings, access controls or Looker report contents changed.

Verification: 28 portal/storage tests passed; app.js syntax check passed; Cloud Build container import smoke passed. Local browser checked overview, populated maps, payment table and assistant layout. Authenticated production overview verified after deployment. Screenshot: outputs/project_audit/20261016_final/workspace_professional_live.jpg.

This is a visual refinement release, not a new model-performance or full operational acceptance result.

Named-area follow-up: revision cp2-portal-00027-jt4 replaces visible coordinates with district selectors in both comparison forms. Approximate centre is labelled. Browser comparison tested Petaling 10 km (13 evaluated services, 5 uncertain boundary matches excluded). 28 portal checks passed. Build d6657d79-d05a-42ce-a566-5aca0d0f9963. Screenshot named_area_picker_live.jpg.
