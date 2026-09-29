"""Release safety checks without live Google calls."""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from scripts import cp2_reporting_release as release


def test_manifest_pins_every_approved_source_and_payment_sidecar():
    sheets = {tab: {"table_name": f"{tab.lower().replace(' ', '_')}_{'a' * 64}",
                     "metadata": {"extracted_at": "2026-09-28T00:00:00+00:00"}}
              for tab in release.TAB_VARS | {"2026": "prospects_snapshot_id"}}
    calendar = {"table_name": "calendar_events_" + "b" * 64,
                "metadata": {"extracted_at": "2026-09-28T00:00:00+00:00"}}
    serials = {"table_name": "payments_date_serials_" + "c" * 64,
               "extracted_at": "2026-09-28T00:01:00+00:00"}
    manifest = release.public_manifest("20260928000000abcdef", sheets, calendar, serials)
    manifest["derived_quality_tables"] = {"calendar_geocodes": "calendar_event_geocodes_for_" + "b" * 64}
    variables = release.dbt_variables(manifest)
    assert variables["payments_snapshot_table"] == sheets["PAYMENTS"]["table_name"]
    assert variables["payments_date_serials_snapshot_table"] == serials["table_name"]
    assert variables["release_schema_prefix"] == "cp2r_20260928000000abcdef_"
    del sheets["WARRANTY CLAIM"]
    with pytest.raises(ValueError, match="Incomplete"):
        release.public_manifest("20260928000000abcdef", sheets, calendar, serials)


@dataclass
class FakeView:
    table_type: str = "VIEW"
    view_query: str = "SELECT 1 AS old_value"
    description: str = "old"


class FailingClient:
    def __init__(self):
        self.tables = {"p.silver.a": FakeView(), "p.gold.b": FakeView()}
        self.updates = 0

    def get_table(self, identifier):
        import copy
        return copy.copy(self.tables[identifier])

    def update_table(self, table, fields):
        self.updates += 1
        if self.updates == 2:
            raise RuntimeError("Injected second-view update failure")
        # A real Table has full_id; this fake locates the one matching its SQL.
        key = "p.silver.a" if "silver.a" in table.view_query or self.updates == 3 else "p.gold.b"
        self.tables[key] = table


def test_partial_promotion_restores_prior_view(monkeypatch, tmp_path):
    client = FailingClient()
    monkeypatch.setattr(release, "PROJECT", "p")
    inventory = [("silver", "a", "cp2r_1_silver"), ("gold", "b", "cp2r_1_gold")]
    monkeypatch.setattr(release, "safe_json", lambda path, value: None)
    monkeypatch.setattr(release, "persist_view_backups", lambda client, run_id, value: None)
    with pytest.raises(RuntimeError, match="Injected"):
        release.promote(client, inventory, tmp_path)
    assert client.tables["p.silver.a"].view_query == "SELECT 1 AS old_value"
    assert client.tables["p.gold.b"].view_query == "SELECT 1 AS old_value"


def test_source_exit_is_audited_as_failed_without_promotion(monkeypatch, tmp_path):
    statuses = []

    class Client:
        def close(self):
            pass

    monkeypatch.setenv("NOMOBUG_BQ_UPLOAD_APPROVED", "yes")
    monkeypatch.setattr(release, "ROOT", tmp_path)
    monkeypatch.setattr(release.bigquery, "Client", lambda **kwargs: Client())
    monkeypatch.setattr(release, "ensure_audit", lambda client: None)
    monkeypatch.setattr(release, "audit", lambda client, run_id, status, *args: statuses.append(status))
    monkeypatch.setattr(release.cp2_pipeline, "source_stage",
                        lambda run_dir: (_ for _ in ()).throw(SystemExit("Missing token")))
    with pytest.raises(SystemExit, match="Missing token"):
        release.run()
    assert statuses == ["STARTED", "FAILED"]
