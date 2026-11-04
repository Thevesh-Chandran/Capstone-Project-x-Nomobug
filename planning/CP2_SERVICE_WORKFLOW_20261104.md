# Service follow-up workspace

The main flow is now: review the linked record, contact the customer, record the outcome, and arrange another visit when appropriate. Payment reminders, customer history, booking and maps support that flow. Historical evidence and current service records have separate status messages.

All eligible services are shown by default; optional score-based limits are viewing controls, not a claim that staff only have time to contact a fraction of clients. The historical ranking comparison is an assessment, not a contact policy. The original frozen model and the separate comparison-pilot approval gate are unchanged.

Production: https://cp2-portal-fav22krh7q-as.a.run.app/#today . Local preview: http://127.0.0.1:8094/#today . The 4 November reporting release is published and its private business snapshots are current. A Cloud Run recovery execution exported 230 recent services for the separate return-risk workflow using that same approved release. The daily reporting job now includes this export; its five-minute website cache may delay display after publication. No customer scores were invented and no original experiment receipts were recreated.

Checks: 65 focused Python workflow checks, both calendar/follow-up UI checks, edited JavaScript syntax, and browser checks of the landing/follow-up views passed. Browser console had no captured errors. Screenshots: outputs/website_design/20261104_service_workflow/.

The Oracle/Metabase setup is separate and still needs the Oracle account and actual free capacity. This workflow does not prove model improvement or establish a reduction in return visits.
