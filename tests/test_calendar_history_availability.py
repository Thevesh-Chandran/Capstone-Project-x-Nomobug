"""Backdated Calendar records must not contribute prediction-time histories."""
from pathlib import Path
import sqlite3

from jinja2 import Environment
import pytest

ROOT = Path(__file__).resolve().parents[1]


def availability_sql():
    source = (ROOT / "dbt/macros/calendar_history_available.sql").read_text()
    return Environment().from_string(source).make_module().calendar_history_available("h", "a")


@pytest.mark.parametrize("relationship", ["package", "property", "area"])
def test_backdated_future_created_history_is_excluded_for_every_relationship(relationship):
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
        create table anchors(event_end_ts text, package text, property text, area text);
        create table history(event_created_ts text, package text, property text, area text, claim integer);
        insert into anchors values ('2026-01-15T12:00:00', 'package', 'property', 'area');
    """)
    identifiers = {name: (name if name == relationship else "other")
                   for name in ["package", "property", "area"]}
    rows = [(created, identifiers["package"], identifiers["property"], identifiers["area"], 1)
            for created in ["2026-01-14T12:00:00", "2026-01-15T12:00:00",
                            "2026-01-16T12:00:00", None]]
    connection.executemany("insert into history values (?, ?, ?, ?, ?)", rows)
    # All fixture visits happened before the anchor. Only creation time changes.
    query = f"""select count(h.claim), sum(h.claim)
        from anchors a left join history h
          on h.{relationship}=a.{relationship} and {availability_sql()}"""
    assert connection.execute(query).fetchone() == (2, 2)
    connection.close()


def test_history_creation_gate_is_shared_by_all_history_predictors():
    source = (ROOT / "dbt/macros/warranty_anchor_dataset_sql.sql").read_text()
    links = source.split("), history_links as (", 1)[1].split("), histories as (", 1)[0]
    assert links.count("and {{ calendar_history_available('h', 'a') }}") == 3
    assert links.count("h.event_date_local < a.event_date_local") == 3
    histories = source.split("), histories as (", 1)[1].split("), outcomes as (", 1)[0]
    assert "left join history_links l on l.anchor_row = a.calendar_event_row" in histories
    assert "h.calendar_event_row = l.history_row" in histories
