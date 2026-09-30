"""Grant only the existing CP2 datasets needed by the reporting job.

The job can create its own candidate datasets through project bigquery.user.
This script deliberately does not grant project-wide dataEditor or dataViewer.
"""
from __future__ import annotations

import argparse

from google.cloud import bigquery


PROJECT = "profound-keel-500007-s4"
REGION = "asia-southeast1"
WRITABLE = ("bronze", "silver", "gold", "audit", "quality")
READ_ONLY = ("analytics_ml",)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Update dataset ACLs")
    parser.add_argument("--collector", action="store_true", help="Grant the prospective collector its narrower dataset access")
    args = parser.parse_args()
    principal = (f"cp2-prospective-job@{PROJECT}.iam.gserviceaccount.com" if args.collector
                 else f"cp2-reporting-job@{PROJECT}.iam.gserviceaccount.com")
    grants = ([(name, "READER") for name in
               ("bronze", "silver", "gold", "quality", "analytics_ml")]
              + [("audit", "WRITER")]) if args.collector else (
              [(name, "WRITER") for name in WRITABLE]
              + [(name, "READER") for name in READ_ONLY])
    client = bigquery.Client(project=PROJECT, location=REGION)
    try:
        for name, role in grants:
            dataset = client.get_dataset(f"{PROJECT}.{name}")
            if dataset.location.lower() != REGION:
                raise ValueError(f"Unexpected dataset region: {name}")
            entries = list(dataset.access_entries)
            matching = [entry for entry in entries
                        if entry.entity_type == "userByEmail" and entry.entity_id == principal]
            if matching and any(entry.role != role for entry in matching):
                if not (name == "quality" and role == "WRITER" and
                        all(entry.role == "READER" for entry in matching)):
                    raise ValueError(f"Existing different access for {name}; review manually")
            needs_update = not matching or any(entry.role != role for entry in matching)
            if needs_update and args.apply:
                entries = [entry for entry in entries if not (
                    entry.entity_type == "userByEmail" and entry.entity_id == principal
                )]
                entries.append(bigquery.AccessEntry(role=role, entity_type="userByEmail",
                                                    entity_id=principal))
                dataset.access_entries = entries
                client.update_dataset(dataset, ["access_entries"])
            state = "present" if not needs_update else ("granted" if args.apply else "planned")
            print(f"{name}: {role} {state}")
    finally:
        client.close()


if __name__ == "__main__":
    main()
