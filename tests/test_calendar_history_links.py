"""The optimized three-join history must preserve the gated OR-join pairs."""
from datetime import date, timedelta
from pathlib import Path
import sqlite3

from jinja2 import Environment
import pytest

ROOT = Path(__file__).resolve().parents[1]


def rendered_link_sql(callback):
    environment = Environment()
    available = environment.from_string(
        (ROOT / "dbt/macros/calendar_history_available.sql").read_text()).make_module()
    template = environment.from_string(
        (ROOT / "dbt/macros/warranty_anchor_dataset_sql.sql").read_text())
    module = template.make_module({
        "ref": lambda model: "events" if model == "calendar_service_event_facts" else model,
        "source": lambda source, table: source + "_" + table,
        "calendar_history_available": available.calendar_history_available,
        "calendar_snapshot_observation_sql": lambda: "select null as observed_through",
    })
    rendered = str(module.warranty_anchor_dataset_sql(callback))
    links = rendered.split("), history_links as (", 1)[1].split("), histories as (", 1)[0]
    # SQLite executes the actual rendered joins. Only BigQuery spelling differs.
    return (links.replace("union distinct", "union")
            .replace("date_sub(a.event_date_local, interval 90 day)", "prior_90_day(a.event_date_local)"))


@pytest.mark.parametrize("callback", [True, False])
def test_links_equal_original_for_overlaps_nulls_backdating_and_area_window(callback):
    connection = sqlite3.connect(":memory:")
    connection.create_function("st_geohash", 2, lambda geography, precision: geography)
    connection.create_function("prior_90_day", 1, lambda value:
                               str(date.fromisoformat(value) - timedelta(days=90)))
    connection.executescript("""
        create table anchors(calendar_event_row integer, sales_record_id text, address_hash text,
            service_geography text, event_date_local text, event_end_ts text);
        create table events(calendar_event_row integer, sales_record_id text, address_hash text,
            service_geography text, event_date_local text, event_created_ts text);
        insert into anchors values
            (1, 'package', 'address', 'area', '2026-04-01', '2026-04-01T12:00:00'),
            (2, 'empty', null, null, '2026-04-01', '2026-04-01T12:00:00'),
            (3, 'no_history', null, null, '2026-04-01', '2026-04-01T12:00:00');
    """)
    rows = [
        (11, 'package', 'address', 'area', '2026-03-01', '2026-03-01T12:00:00'),  # All three paths.
        (12, 'other', 'other', 'area', '2026-01-01', '2026-01-01T12:00:00'),  # Exactly 90d.
        (13, 'other', 'other', 'area', '2025-12-31', '2025-12-31T12:00:00'),  # Area too old.
        (14, 'package', 'other', 'other', '2025-01-01', '2025-01-01T12:00:00'),  # Package remains all history.
        (15, 'other', 'address', 'other', '2025-01-01', '2025-01-01T12:00:00'),  # Property remains all history.
        (16, 'package', 'address', 'area', '2026-03-01', '2026-04-02T12:00:00'),  # Future-created.
        (17, 'package', 'address', 'area', '2026-04-01', '2026-04-01T11:00:00'),  # Same-day visits excluded.
        (18, 'package', 'address', 'area', '2026-03-01', None),  # Unknown creation excluded.
        (19, 'empty', None, None, '2026-03-01', '2026-04-01T12:00:00'),  # Null location, package fallback.
        (20, None, None, None, '2026-03-01', '2026-03-01T12:00:00'),  # Null identifiers cannot match.
    ]
    connection.executemany("insert into events values (?, ?, ?, ?, ?, ?)", rows)
    original = """select a.calendar_event_row, h.calendar_event_row
        from anchors a join events h
          on h.event_date_local < a.event_date_local
         and h.event_created_ts <= a.event_end_ts
         and (h.sales_record_id = a.sales_record_id
              or (a.address_hash is not null and h.address_hash = a.address_hash)
              or (h.event_date_local >= prior_90_day(a.event_date_local)
                  and st_geohash(h.service_geography, 4) = st_geohash(a.service_geography, 4)))"""
    expected = set(connection.execute(original))
    actual_rows = list(connection.execute(rendered_link_sql(callback)))
    assert set(actual_rows) == expected == {(1, 11), (1, 12), (1, 14), (1, 15), (2, 19)}
    assert len(actual_rows) == len(expected)  # Overlapping paths count only once.
    assert not any(anchor == 3 for anchor, history in actual_rows)
    connection.close()
