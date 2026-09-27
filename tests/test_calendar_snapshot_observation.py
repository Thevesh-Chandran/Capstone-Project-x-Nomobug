"""Ensure both model targets use extraction coverage rather than appointments."""
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
TABLE = "calendar_events_" + "a" * 64


def rendered_sql():
    relation = SimpleNamespace(database="project", schema="bronze", identifier=TABLE)
    template = Environment().from_string(
        (ROOT / "dbt/macros/calendar_snapshot_observation_sql.sql").read_text())
    return str(template.make_module({"source": lambda name, table: relation})
               .calendar_snapshot_observation_sql())


def test_watermark_reads_metadata_of_the_actual_controlling_source():
    sql = rendered_sql()
    assert "`project.bronze.INFORMATION_SCHEMA.TABLE_OPTIONS`" in sql
    assert "table_name = '" + TABLE + "'" in sql
    assert "concat('calendar_events_', snapshot_id) = '" + TABLE + "'" in sql
    assert "max(event_date_local)" not in sql


def test_missing_metadata_fails_closed_and_extraction_day_is_incomplete():
    sql = rendered_sql()
    assert "metadata_row_count = 1" in sql
    assert "source_timezone = 'Asia/Kuala_Lumpur'" in sql
    assert "extracted_at <= current_timestamp()" in sql
    assert "regexp_contains(extracted_at_raw" in sql
    assert "date_sub(date(extracted_at, 'Asia/Kuala_Lumpur'), interval 1 day)" in sql
    assert "date_sub(current_date('Asia/Kuala_Lumpur'), interval 1 day)" in sql
    assert "else cast(null as date)" in sql


def test_callback_and_entitlement_targets_share_the_coverage_watermark():
    source = (ROOT / "dbt/macros/warranty_anchor_dataset_sql.sql").read_text()
    observation = source.split("with observation as (", 1)[1].split("), uncertain_packages", 1)[0]
    assert "{{ calendar_snapshot_observation_sql() }}" in observation
    assert "max(event_date_local)" not in observation
    assert "date_add(event_date_local, interval 30 day) <= o.observed_through" in source
