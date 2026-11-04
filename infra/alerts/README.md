# Email alert when the daily reporting job fails

Why: the reporting job stopped from 29 October to 4 November 2026 and nobody was told. This policy emails the owner when an execution of `cp2-reporting-daily` fails, or when no execution has succeeded for 26 hours (one missed 06:00 run plus a two-hour margin). Alerting uses Cloud Monitoring; check project billing rather than assuming alerts have no charge.

Run once (project `profound-keel-500007-s4`):

```sh
# 1. Email channel (replace the address); prints the channel name
gcloud beta monitoring channels create --display-name="CP2 owner email" \
  --type=email --channel-labels=email_address=OWNER_EMAIL --project=profound-keel-500007-s4

# 2. Policy, linked to that channel
gcloud alpha monitoring policies create --policy-from-file=infra/alerts/reporting_job_alert_policy.json \
  --notification-channels=CHANNEL_NAME_FROM_STEP_1 --project=profound-keel-500007-s4
```

Test: run the job once with a deliberately wrong variable in a disposable execution, or check "Incidents" after the next real failure. Do not break the production schedule to test.


Enabled 4 November 2026 for the owner email. The no-success condition uses a 24-hour successful-execution sum below one for two hours, including missing data, rather than an unsupported 26-hour absence duration. A delivery test is a one-off failed execution with no source or Gold writes; the normal schedule remains unchanged.
