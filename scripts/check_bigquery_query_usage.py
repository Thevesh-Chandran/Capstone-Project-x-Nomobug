"""Show recent BigQuery job usage without running a billable query."""

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from google.cloud import bigquery

client = bigquery.Client(project="profound-keel-500007-s4")
since = datetime.now(timezone.utc) - timedelta(days=3)
jobs = client.list_jobs(min_creation_time=since, max_results=1000)
daily = defaultdict(lambda: [0, 0])
recent = []

for job in jobs:
    if job.job_type != "query":
        continue
    day = job.created.astimezone(ZoneInfo("America/Los_Angeles")).date()
    processed = int(job.total_bytes_processed or 0)
    billed = int(job.total_bytes_billed or 0)
    daily[day][0] += processed
    daily[day][1] += billed
    recent.append((processed, job.created, job.job_id))

for day, (processed, billed) in sorted(daily.items()):
    print(f"{day} Pacific: {processed / 2**30:.3f} GiB processed, "
          f"{billed / 2**30:.3f} GiB billed across listed query jobs")

print("Largest recent query jobs (GiB processed):")
for processed, created, job_id in sorted(recent, reverse=True)[:8]:
    print(f"  {processed / 2**30:.3f}  {created.isoformat()}  {job_id}")

print("Read-only job metadata; a job can be missing if permissions or page limits restrict listing.")
client.close()
