"""Read-only KPI acceptance checks against the exact deployed source snapshots.

Recompute from Bronze using Python, rather than calling dbt's SQL helpers.
Only aggregate results and opaque example IDs are printed. Row evidence is
saved under ignored outputs/. This validates recorded activity, not settlement,
completed treatments, unique customers, or biological pest recurrence.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
PROJECT = "profound-keel-500007-s4"
LOCATION = "asia-southeast1"
MAXIMUM_BYTES_BILLED = 100 * 1024 * 1024
MYT = ZoneInfo("Asia/Kuala_Lumpur")


def amount(value: Any) -> Decimal | None:
    """Strict MYR cell conversion; ambiguous annotations are not guessed."""
    text = str(value or "").strip().upper()
    if not re.fullmatch(r"(?:RM\s*)?-?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?", text):
        return None
    return Decimal(re.sub(r"^RM\s*", "", text).replace(",", ""))


def references(value: Any) -> list[str]:
    text = str(value or "").strip().upper()
    if not re.fullmatch(r"CUST\s*\d+(?:\s*[,/]\s*(?:CUST\s*)?\d+)*", text):
        return []
    return ["CUST" + re.sub(r"^CUST\s*", "", part.strip())
            for part in re.split(r"\s*[,/]\s*", text)]


def named_date(value: Any, year: int | None = None) -> date | None:
    text = str(value or "").strip()
    if year is not None:
        text = f"{text} {year}"
    for pattern in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            pass
    return None


def serial_date(value: Any, cell_type: str) -> date | None:
    if cell_type != "serial":
        return None
    try:
        numeric = Decimal(str(value))
        if not numeric.is_finite():
            return None
        return date(1899, 12, 30) + timedelta(days=int(numeric.to_integral_value(rounding=ROUND_FLOOR)))
    except (InvalidOperation, OverflowError, ValueError):
        return None


def month(value: date | None) -> str:
    return value.replace(day=1).isoformat() if value else "undated"


def local_date(value: Any) -> date | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(MYT).date()
    except ValueError:
        return None


def opaque_id(source: str, key: Any) -> str:
    return hashlib.sha256(f"{source}:{key}".encode()).hexdigest()[:12]


def primitive(value: Any) -> Any:
    if isinstance(value, (Decimal, date, datetime)):
        return str(value)
    if isinstance(value, dict):
        return {str(k): primitive(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [primitive(v) for v in value]
    return value


def keyed(rows: list[dict], key: str) -> dict[Any, dict]:
    mapping = {r[key]: r for r in rows}
    if len(mapping) != len(rows):
        raise ValueError(f"Duplicate {key}; grain check failed")
    return mapping


def compare_rows(expected: list[dict], actual: list[dict], key: str,
                 columns: list[str], source: str) -> dict:
    """Exact membership and value comparison; dropped/expanded rows fail."""
    left, right = keyed(expected, key), keyed(actual, key)
    missing, extra = set(left) - set(right), set(right) - set(left)
    bad = []
    for row_key in sorted(set(left) & set(right), key=str):
        for column in columns:
            wanted, observed = left[row_key].get(column), right[row_key].get(column)
            if wanted != observed:
                # Full row values remain in private_source_evidence.json. Avoid
                # copying a free-text B2B status or future source cell into
                # the compact summary, which is easier to share accidentally.
                bad.append({"example_id": opaque_id(source, row_key), "field": column})
    return {"checked_expected_rows": len(left), "checked_actual_rows": len(right),
            "missing_rows": len(missing), "unexpected_rows": len(extra),
            "value_mismatches": len(bad), "mismatch_examples": bad[:10],
            "status": "pass" if not (missing or extra or bad) else "fail"}


def expected_sales(raw: list[dict], cancelled: set[str]) -> list[dict]:
    candidates = []
    for row in sorted(raw, key=lambda r: r["source_sheet_row"]):
        ids = references(row["source_column_007"])
        if len(ids) != 1:
            continue
        year_match = re.search(r"(?:19|20)\d{2}", row["source_column_003"] or "")
        candidates.append((row, ids[0], int(year_match.group()) if year_match else None))
    output = []
    for index, (row, sale_id, recorded_year) in enumerate(candidates):
        previous = next((c[2] for c in reversed(candidates[:index]) if c[2] is not None), None)
        following = next((c[2] for c in candidates[index + 1:] if c[2] is not None), None)
        year = recorded_year
        year_source = "entry_timestamp"
        if year is None and previous is None and following is not None:
            year, year_source = following, "early_sequence_inferred"
        elif year is None and previous is not None and previous == following:
            year, year_source = previous, "adjacent_timestamps_inferred"
        elif year is None:
            year_source = "unresolved"
        close = re.sub(r"[ /]+", " ", str(row["source_column_004"] or "").strip())
        close = re.sub("Sept", "Sep", close, flags=re.I).replace("-", " ")
        parsed = named_date(close, year) if year else None
        if named_date(close, 2000) is None:
            year_source = "unresolved"
        premise = str(row["source_column_013"] or "").strip().upper()
        premise = ("COMMERCIAL" if premise.startswith("COMM") else
                   "RESIDENTIAL" if premise.startswith("RES") else
                   "VEHICLE" if premise in ("CAR", "VAN", "VEHICLE") else "UNKNOWN")
        session_text = str(row["source_column_014"] or "").strip()
        sessions = int(session_text) if re.fullmatch(r"[+-]?\d+", session_text) else None
        eligible = premise == "RESIDENTIAL" and sessions in (3, 4, 6, 12)
        category = ("INELIGIBLE_COMMERCIAL" if premise == "COMMERCIAL" else
                    "INELIGIBLE_RESIDENTIAL_1X" if premise == "RESIDENTIAL" and sessions == 1 else
                    "ELIGIBLE_RESIDENTIAL_PACKAGE" if eligible else "REVIEW_UNDEFINED_POLICY")
        policy = ("POST_FINAL_SERVICE_30D" if eligible and sessions == 3 else
                  "FIRST_SERVICE_THROUGH_30D_AFTER_FINAL_UNLIMITED_CLAIMS" if eligible else
                  "NO_WARRANTY" if category.startswith("INELIGIBLE") else "REVIEW_UNDEFINED_POLICY")
        output.append({"source_sheet_row": row["source_sheet_row"], "sales_record_id": sale_id,
                       "sale_total_rm": amount(row["source_column_028"]), "closed_date": parsed,
                       "closed_date_year_source": year_source, "include_in_sale_count": sale_id not in cancelled,
                       "premise_type": premise, "package_sessions_recorded": sessions,
                       "warranty_policy_eligible": eligible, "warranty_policy_category": category,
                       "warranty_policy_rule": policy})
    return output


def expected_payments(raw: list[dict], serials: list[dict]) -> list[dict]:
    dates = keyed(serials, "source_sheet_row")
    output = []
    for row in raw:
        sidecar = dates.get(row["source_sheet_row"])
        if sidecar is None:
            raise ValueError("Payment date sidecar missing source row")
        if str(row["source_column_001"] or "") != str(sidecar["payment_date_display_raw"] or ""):
            raise ValueError("Payment date sidecar differs from source display date")
        ids = references(row["source_column_002"])
        text = str(row["source_column_002"] or "").strip()
        status = ("missing" if not text else "unrecognized" if not ids else
                  "repeated_reference_review" if len(ids) != len(set(ids)) else
                  "combined" if len(ids) > 1 else "single")
        output.append({"source_sheet_row": row["source_sheet_row"],
                       "payment_date": serial_date(sidecar["unformatted_value"], sidecar["unformatted_type"]),
                       "payment_date_cell_type": sidecar["unformatted_type"],
                       "amount_rm": amount(row["source_column_003"]),
                       "reference_status": status, "referenced_sale_count": len(ids)})
    return output


def calendar_category(summary: str, status: str, review: str | None = None) -> str:
    title = (summary or "").upper()
    if (status or "").upper() == "CANCELLED":
        return "cancelled"
    if re.search(r"\b(?:CHECK|REVIEW|CALCULATE)\b.*\bCONVERSION\s+RATE\b", title):
        return "administrative"
    if review == "Confirmed warranty claim":
        return "warranty"
    if review == "Unclear":
        return "label_unresolved"
    allow_claim = review != "Not a warranty claim"
    without_entitlement = re.sub(r"\b(?:NO|WITHOUT)\s+WARRANTY\b", "", title)
    if allow_claim and re.search(r"\b(?:WARRANTY|CLAIMS?|CALLBACK)\b", without_entitlement):
        return "warranty"
    if re.search(r"\b(?:CONSULTATION|INSPECTION)\b", title):
        return "consultation"
    sequence = re.search(r"\b(\d{1,2})\s*/\s*(\d{1,2})\b", title)
    if allow_claim and sequence and int(sequence[1]) > int(sequence[2]):
        return "warranty"
    if re.search(r"\b(?:EXTRA|COMPLIMENTARY|FOLLOW[- ]?UP)\b", title):
        return "complimentary"
    return "service" if sequence else "other"


def expected_calendar(raw: list[dict], reviews: list[dict]) -> list[dict]:
    overrides = {(int(r["calendar_event_row"]), r["event_id"]): r["review_label"] for r in reviews}
    output = []
    for row in raw:
        label = overrides.get((int(row["calendar_event_row"]), row["event_id"]))
        category = calendar_category(row["summary"], row["status"], label)
        if row["status"] != "confirmed" or category not in ("service", "warranty", "extra_visit_candidate", "complimentary"):
            continue
        output.append({"calendar_event_row": row["calendar_event_row"],
                       "event_date_local": local_date(row["start_raw"]),
                       "event_category": category, "warranty_claim_candidate": category == "warranty"})
    return output


def monetary_months(rows: list[dict], kind: str, today: date) -> list[dict]:
    grouped: dict[str, dict] = {}
    for row in rows:
        when = row["closed_date" if kind == "sales" else "payment_date"]
        key = month(when)
        eligible = when is not None and when <= today and (kind != "sales" or row["include_in_sale_count"])
        names = ("package_rows", "countable_package_rows", "recorded_package_face_value_rm") if kind == "sales" else (
            "payment_rows", "dated_nonfuture_rows", "recorded_payment_entry_amount_rm")
        group = grouped.setdefault(key, {"month": key, names[0]: 0, names[1]: 0, names[2]: None})
        group[names[0]] += 1
        group[names[1]] += int(eligible)
        value = row["sale_total_rm" if kind == "sales" else "amount_rm"]
        if eligible and value is not None:
            group[names[2]] = (group[names[2]] or Decimal(0)) + value
    return list(grouped.values())


def expected_prospects(raw: list[dict]) -> list[dict]:
    output = []
    for row in raw:
        # Phone or first staff reply establishes an enquiry candidate; ignore
        # automatic follow-up dates. Phone values never enter public evidence.
        if not (str(row["source_column_002"] or "").strip() or str(row["source_column_013"] or "").strip()):
            continue
        text = re.sub(r"[-\s]+", " ", str(row["source_column_013"] or "").strip())
        reply = named_date(text, 2026) if re.fullmatch(r"\d{1,2} [A-Za-z]+", text) else None
        status = str(row["source_column_008"] or "").strip().upper()
        output.append({"source_sheet_row": row["source_sheet_row"], "first_reply_date": reply,
                       "conversation_status": "CLOSED" if status in ("CLOSED", "CLOOSED") else "OPEN" if status == "OPEN" else None,
                       "remark_is_exact_won": str(row["source_column_012"] or "").strip().upper() == "WON"})
    return output


class Reader:
    def __init__(self, client: Any, project: str):
        self.client, self.project = client, project
        self.jobs: list[dict] = []
        self.lineage: list[dict] = []

    def read(self, table: str, columns: list[str]) -> list[dict]:
        from google.cloud import bigquery
        if not re.fullmatch(r"[a-z0-9_-]+\.[a-z0-9_]+\.[a-z0-9_]+", table):
            raise ValueError("Invalid table identifier")
        if any(not re.fullmatch(r"[a-z0-9_]+", column) for column in columns):
            raise ValueError("Invalid column identifier")
        sql = f"SELECT {', '.join(columns)} FROM `{table}`"
        settings = bigquery.QueryJobConfig(maximum_bytes_billed=MAXIMUM_BYTES_BILLED, use_query_cache=False)
        job = self.client.query(sql, job_config=settings)
        rows = [dict(row) for row in job.result()]
        self.jobs.append({"table": table, "columns": columns, "job_id": job.job_id,
                          "bytes_processed": job.total_bytes_processed, "bytes_billed": job.total_bytes_billed})
        return rows

    def source(self, silver_view: str, prefix: str) -> str:
        view = self.client.get_table(f"{self.project}.silver.{silver_view}")
        if view.table_type != "VIEW":
            raise ValueError("Source lineage requires a deployed Silver view")
        matches = set(re.findall(rf"\b{prefix}_[0-9a-f]{{64}}\b", view.view_query or ""))
        if len(matches) != 1:
            raise ValueError(f"Ambiguous {silver_view} snapshot lineage")
        name = matches.pop()
        return self.snapshot(name)

    def snapshot(self, name: str) -> str:
        table = self.client.get_table(f"{self.project}.bronze.{name}")
        metadata = json.loads(table.description or "{}")
        if table.table_type != "TABLE" or metadata.get("snapshot_id") != name.rsplit("_", 1)[1]:
            raise ValueError("Snapshot identity metadata mismatch")
        if metadata.get("source_row_count") is not None and metadata["source_row_count"] != table.num_rows:
            raise ValueError("Snapshot row-count metadata mismatch")
        self.lineage.append({"table": f"{self.project}.bronze.{name}", "extracted_at": metadata.get("extracted_at"),
                             "source_tab": metadata.get("source_tab"), "source_row_count": table.num_rows})
        return f"{self.project}.bronze.{name}"


def run_validation(reader: Reader, today: date) -> tuple[dict, dict]:
    source_names = {
        "sales": reader.source("sales", "sales"), "payments": reader.source("payments", "payments"),
        "calendar": reader.source("calendar_events", "calendar_events"),
        "refund": reader.source("refund", "refund"), "claims": reader.source("warranty_claim", "warranty_claim"),
        "prospects": reader.source("prospects_2026", "prospects_2026"), "b2b": reader.source("b2b_follow_up", "b2b_follow_up"),
    }
    import yaml
    sources = yaml.safe_load((ROOT / "dbt/models/operational_sources.yml").read_text(encoding="utf-8"))
    identifier = next(t["identifier"] for s in sources["sources"] if s["name"] == "operational_bronze"
                      for t in s["tables"] if t["name"] == "payments_date_serials")
    source_names["serials"] = reader.snapshot(identifier)
    raw = {}
    selections = {
        "sales": [3, 4, 7, 13, 14, 26, 28], "payments": [1, 2, 3],
        "refund": [1, 2, 7, 10], "claims": [1, 2, 7], "prospects": [2, 8, 12, 13], "b2b": [3, 7],
    }
    for source, positions in selections.items():
        raw[source] = reader.read(source_names[source], ["source_sheet_row"] + [f"source_column_{p:03}" for p in positions])
    raw["calendar"] = reader.read(source_names["calendar"], ["calendar_event_row", "event_id", "status", "summary", "start_raw"])
    raw["serials"] = reader.read(source_names["serials"], ["source_sheet_row", "payment_date_display_raw", "unformatted_value", "unformatted_type"])
    with (ROOT / "dbt/seeds/sale_disposition_overrides.csv").open(encoding="utf-8", newline="") as stream:
        cancellations = {r["sales_record_id"] for r in csv.DictReader(stream)}
    with (ROOT / "dbt/seeds/calendar_warranty_review_overrides.csv").open(encoding="utf-8", newline="") as stream:
        reviews = list(csv.DictReader(stream))
    expected = {"sales": expected_sales(raw["sales"], cancellations),
                "payments": expected_payments(raw["payments"], raw["serials"]),
                "calendar": expected_calendar(raw["calendar"], reviews),
                "prospects": expected_prospects(raw["prospects"])}
    checks, actual = {}, {}
    specifications = {
        "sales": ("gold.sales_package_facts", "source_sheet_row", ["sales_record_id", "sale_total_rm", "closed_date", "closed_date_year_source", "include_in_sale_count", "premise_type", "package_sessions_recorded", "warranty_policy_eligible", "warranty_policy_category", "warranty_policy_rule"]),
        "payments": ("gold.payment_record_facts", "source_sheet_row", ["payment_date", "payment_date_cell_type", "amount_rm", "reference_status", "referenced_sale_count"]),
        "calendar": ("gold.calendar_service_event_facts", "calendar_event_row", ["event_date_local", "event_category", "warranty_claim_candidate"]),
        "prospects": ("silver.prospects_2026", "source_sheet_row", ["first_reply_date", "conversation_status", "remark_is_exact_won", "row_class"]),
    }
    for name, (table, key, columns) in specifications.items():
        actual[name] = reader.read(f"{reader.project}.{table}", [key] + columns)
        selected = [r for r in actual[name] if r["row_class"] == "prospect_candidate"] if name == "prospects" else actual[name]
        checks[f"{name}_source_to_reporting_rows"] = compare_rows(expected[name], selected, key,
                                                                  [c for c in columns if c != "row_class"], name)
    # Refund and formal claim counts retain source-record grain, independent of
    # Calendar callbacks. Every raw row is checked, including unresolved dates.
    sale_ids = {r["sales_record_id"] for r in expected["sales"]}
    for name, table in (("refund", "refund_record_facts"), ("claims", "warranty_claim_record_facts")):
        prepared = []
        for row in raw[name]:
            sale_id = str(row["source_column_002"] or "").strip().upper()
            linked = sale_id if sale_id in sale_ids else None
            common = {"source_sheet_row": row["source_sheet_row"], "sales_record_id": linked,
                      "sale_link_status": "exact_sale_id" if linked else "unmatched_source_id"}
            if name == "refund":
                value = amount(row["source_column_007"])
                status = str(row["source_column_010"] or "").strip().upper()
                common.update(recorded_refund_amount_rm=value, refund_amount_needs_review=value is None,
                              recorded_refund_status="recorded_complete" if status == "COMPLETE" else "not_recorded" if not status else "other_status_needs_review")
            else:
                when = named_date(row["source_column_001"])
                indicator = str(row["source_column_007"] or "").strip().upper()
                common.update(recorded_claim_date=when, claim_date_needs_review=when is None,
                              source_refund_indicator="recorded_yes" if indicator == "YES" else "recorded_no" if indicator == "NO" else "date_text_recorded" if named_date(indicator) else "other_needs_review")
            prepared.append(common)
        expected[name] = prepared
        fields = [c for c in prepared[0] if c != "source_sheet_row"] if prepared else []
        actual[name] = reader.read(f"{reader.project}.gold.{table}", ["source_sheet_row"] + fields)
        checks[f"{name}_source_to_reporting_rows"] = compare_rows(prepared, actual[name], "source_sheet_row", fields, name)
    refund_monthly = defaultdict(Counter)
    for source_row, row in zip(raw["refund"], expected["refund"]):
        group = refund_monthly[month(named_date(source_row["source_column_001"]))]
        group["refund_source_rows"] += 1
        group["linked_refund_rows"] += int(row["sale_link_status"] == "exact_sale_id")
        group["unmatched_refund_rows"] += int(row["sale_link_status"] == "unmatched_source_id")
        group["recorded_complete_rows"] += int(row["recorded_refund_status"] == "recorded_complete")
        group["amount_review_rows"] += int(row["refund_amount_needs_review"])
        group["date_review_rows"] += int(named_date(source_row["source_column_001"]) is None)
    names = ["refund_source_rows", "linked_refund_rows", "unmatched_refund_rows", "recorded_complete_rows", "amount_review_rows", "date_review_rows"]
    expected["refund_monthly"] = [{"month": key, **{name: count[name] for name in names}} for key, count in refund_monthly.items()]
    monthly = reader.read(f"{reader.project}.gold.dashboard_refund_monthly", ["refund_month"] + names)
    actual["refund_monthly"] = [{"month": month(r["refund_month"]), **{name: r[name] for name in names}} for r in monthly]
    checks["refund_monthly_from_bronze"] = compare_rows(expected["refund_monthly"], actual["refund_monthly"], "month", names, "refund")
    for name, table, date_column, names in (
        ("sales", "sales_monthly_recorded", "closed_month", ["package_rows", "countable_package_rows", "recorded_package_face_value_rm"]),
        ("payments", "payments_monthly_recorded", "payment_month", ["payment_rows", "dated_nonfuture_rows", "recorded_payment_entry_amount_rm"]),
    ):
        expected[f"{name}_monthly"] = monetary_months(expected[name], name, today)
        monthly = reader.read(f"{reader.project}.gold.{table}", [date_column] + names)
        actual[f"{name}_monthly"] = [{"month": month(r[date_column]), **{n: r[n] for n in names}} for r in monthly]
        checks[f"{name}_monthly_from_bronze"] = compare_rows(expected[f"{name}_monthly"], actual[f"{name}_monthly"], "month", names, name)
    calendar_monthly = defaultdict(Counter)
    for row in expected["calendar"]:
        when = row["event_date_local"]
        if when is not None and when.year == 2026:
            group = calendar_monthly[month(when)]
            group["scheduled_service_event_rows"] += 1
            group["normal_package_service_event_rows"] += int(row["event_category"] == "service")
            group["warranty_claim_event_rows"] += int(row["warranty_claim_candidate"])
            group["generic_complimentary_event_rows"] += int(row["event_category"] == "complimentary")
    names = ["scheduled_service_event_rows", "normal_package_service_event_rows", "warranty_claim_event_rows", "generic_complimentary_event_rows"]
    expected["calendar_monthly"] = [{"month": key, **{name: count[name] for name in names}} for key, count in calendar_monthly.items()]
    monthly = reader.read(f"{reader.project}.gold.dashboard_service_monthly", ["service_month"] + names)
    actual["calendar_monthly"] = [{"month": month(r["service_month"]), **{name: r[name] for name in names}} for r in monthly]
    checks["calendar_monthly_from_bronze"] = compare_rows(expected["calendar_monthly"], actual["calendar_monthly"], "month", names, "calendar")
    prospect_monthly = defaultdict(Counter)
    for row in expected["prospects"]:
        group = prospect_monthly[month(row["first_reply_date"])]
        group["prospect_candidate_rows"] += 1
        group["recorded_closed_rows"] += int(row["conversation_status"] == "CLOSED")
        group["recorded_open_rows"] += int(row["conversation_status"] == "OPEN")
        group["exact_won_remark_rows"] += int(row["remark_is_exact_won"])
    names = ["prospect_candidate_rows", "recorded_closed_rows", "recorded_open_rows", "exact_won_remark_rows"]
    expected["prospects_monthly"] = [{"month": key, **{name: count[name] for name in names}} for key, count in prospect_monthly.items()]
    monthly = reader.read(f"{reader.project}.gold.prospect_reply_monthly_recorded", ["first_reply_month"] + names)
    actual["prospects_monthly"] = [{"month": month(r["first_reply_month"]), **{name: r[name] for name in names}} for r in monthly]
    checks["prospects_monthly_from_bronze"] = compare_rows(expected["prospects_monthly"], actual["prospects_monthly"], "month", names, "prospects")
    expected["b2b"] = [{"source_sheet_row": r["source_sheet_row"], "phone_present_candidate": bool(str(r["source_column_003"] or "").strip()),
                        "status_label": str(r["source_column_007"] or "").strip().upper() or None} for r in raw["b2b"]]
    actual["b2b"] = reader.read(f"{reader.project}.silver.b2b_follow_up", ["source_sheet_row", "phone_present_candidate", "status_label"])
    checks["b2b_source_annotations"] = compare_rows(expected["b2b"], actual["b2b"], "source_sheet_row", ["phone_present_candidate", "status_label"], "b2b")
    examples = []
    selectors = [
        ("sales", "cancelled_package", lambda r: not r["include_in_sale_count"]),
        ("sales", "commercial_no_warranty", lambda r: r["premise_type"] == "COMMERCIAL"),
        ("sales", "residential_1x_no_warranty", lambda r: r["warranty_policy_category"] == "INELIGIBLE_RESIDENTIAL_1X"),
        ("sales", "residential_3x_post_final_30d", lambda r: r["package_sessions_recorded"] == 3 and r["warranty_policy_eligible"]),
        ("sales", "residential_subscription_warranty", lambda r: r["package_sessions_recorded"] in (4, 6, 12) and r["warranty_policy_eligible"]),
        ("payments", "combined_payment_counted_once", lambda r: r["reference_status"] == "combined" and r["amount_rm"] is not None),
        ("payments", "ambiguous_payment_kept_unknown", lambda r: r["amount_rm"] is None),
        ("calendar", "calendar_callback", lambda r: r["warranty_claim_candidate"]),
        ("refund", "unresolved_refund_amount", lambda r: r["refund_amount_needs_review"]),
        ("claims", "undated_formal_claim", lambda r: r["claim_date_needs_review"]),
        ("prospects", "recorded_won_annotation", lambda r: r["remark_is_exact_won"]),
    ]
    for source, reason, predicate in selectors:
        row = next((r for r in expected[source] if predicate(r)), None)
        if row:
            key = "calendar_event_row" if source == "calendar" else "source_sheet_row"
            public_values = {k: primitive(v) for k, v in row.items() if k not in (key, "sales_record_id")}
            examples.append({"example_id": opaque_id(source, row[key]), "case": reason, "source": source,
                             "expected_reporting_values": public_values,
                             "status": checks[f"{source}_source_to_reporting_rows"]["status"]})
    def count_status(rows: list[dict], field: str, allowed: set[str] | None = None) -> dict:
        labels = (str(r[field]) for r in rows)
        return dict(Counter(label if allowed is None or label in allowed else "OTHER_SOURCE_TEXT"
                            for label in labels))
    totals = {
        "identified_sales_package_rows": len(expected["sales"]),
        "countable_dated_nonfuture_sales_packages": sum(r["countable_package_rows"] for r in expected["sales_monthly"]),
        "recorded_package_face_value_rm": sum((r["recorded_package_face_value_rm"] or Decimal(0) for r in expected["sales_monthly"]), Decimal(0)),
        "payment_source_rows": len(expected["payments"]),
        "dated_nonfuture_payment_rows": sum(r["dated_nonfuture_rows"] for r in expected["payments_monthly"]),
        "recorded_payment_entry_amount_rm": sum((r["recorded_payment_entry_amount_rm"] or Decimal(0) for r in expected["payments_monthly"]), Decimal(0)),
        "combined_payment_reference_rows": sum(r["reference_status"] == "combined" for r in expected["payments"]),
        "calendar_service_like_rows_all_dates": len(expected["calendar"]),
        "calendar_service_like_rows_2026_all_dates": sum(r["scheduled_service_event_rows"] for r in expected["calendar_monthly"]),
        "calendar_future_service_like_rows_2026": sum(r["event_date_local"] is not None and r["event_date_local"].year == 2026 and r["event_date_local"] > today for r in expected["calendar"]),
        "calendar_callback_signal_rows_2026": sum(r["warranty_claim_event_rows"] for r in expected["calendar_monthly"]),
        "formal_claim_source_rows": len(expected["claims"]),
        "undated_formal_claim_rows": sum(r["claim_date_needs_review"] for r in expected["claims"]),
        "refund_source_rows": len(expected["refund"]),
        "refund_unparsed_amount_rows": sum(r["refund_amount_needs_review"] for r in expected["refund"]),
        "recorded_refund_amount_rm": sum((r["recorded_refund_amount_rm"] or Decimal(0) for r in expected["refund"]), Decimal(0)),
        "prospect_candidate_rows": len(expected["prospects"]),
        "prospect_exact_won_annotation_rows": sum(r["remark_is_exact_won"] for r in expected["prospects"]),
        "b2b_source_rows": len(expected["b2b"]),
        "b2b_phone_present_rows": sum(r["phone_present_candidate"] for r in expected["b2b"]),
        "b2b_status_annotation_counts": count_status(expected["b2b"], "status_label", {
            "PENDING SITE VISIT", "NOT INTERESTED (REMARK)", "NO REPLY", "CHECK WITH BOSS",
            "WON", "INTERESTED", "QUOTATION SENT", "TOO EXPENSIVE", "None"}),
        "sales_warranty_policy_categories": count_status(expected["sales"], "warranty_policy_category"),
        "sales_inferred_close_year_rows": sum(r["closed_date_year_source"].endswith("inferred") for r in expected["sales"]),
    }
    summary = {
        "schema_version": 1, "as_of_local_date": today.isoformat(), "validation_type": "read_only_bronze_python_vs_deployed_reporting",
        "status": "pass_with_business_caveats" if all(c["status"] == "pass" for c in checks.values()) else "needs_revision",
        "checks": checks, "totals": primitive(totals), "real_source_examples": examples, "lineage": reader.lineage,
        "maximum_bytes_billed_per_query": MAXIMUM_BYTES_BILLED,
        "bytes_processed": sum(job["bytes_processed"] or 0 for job in reader.jobs),
        "query_count": len(reader.jobs),
        "caveats": [
            "Validation uses exact deployed immutable snapshots; it does not claim every Sheet or the Calendar warehouse is refreshed to today.",
            "Package face value is not earned revenue; payment entries and COMPLETE refund annotations are not bank-verified settlement.",
            "Service monthly counts include future 2026 appointments, consistently with the scheduled/recorded definition; they are not completed treatments.",
            "Formal Sheet claims and Calendar callback signals are different grains and must not be added as one claim count.",
            "Warranty flags validate native package eligibility only, not every claim's date window or linked 1x+Upsell 2x entitlement.",
            "Prospect WON/CLOSED and B2B statuses are annotations, not reconciled conversion rates or unique customer counts.",
            "Inferred sale-close years remain disclosed estimates; unknown amounts and dates are retained, not replaced by zero.",
        ],
    }
    evidence = {"sources": raw, "expected": expected, "reporting_rows": actual, "query_jobs": reader.jobs}
    return summary, evidence


def private_output(path: Path) -> Path:
    target = path.resolve()
    target.relative_to((ROOT / "outputs").resolve())
    if target.exists():
        raise ValueError("Output directory already exists; historical validation evidence cannot be overwritten")
    return target


def fresh_source_drift(evidence: dict, fresh: dict) -> dict:
    """Compare overlapping source positions without relabelling current Gold.

    Changes in selected KPI inputs and row membership are reported separately.
    Full raw cells and changed row keys stay in private evidence, not output.
    """
    snapshots = fresh.get("snapshots")
    if not isinstance(snapshots, dict):
        raise ValueError("Fresh source artifact has no snapshots mapping")
    tab_names = {"sales": "SALES", "payments": "PAYMENTS", "refund": "REFUND",
                 "claims": "WARRANTY CLAIM", "prospects": "2026", "b2b": "B2B FOLLOW UP"}
    results = {}
    for name, tab in tab_names.items():
        item = snapshots.get(tab)
        if item is None:
            results[tab] = {"status": "fresh_source_not_supplied"}
            continue
        records = item.get("records")
        if not isinstance(records, list):
            raise ValueError("Fresh source records must be a list")
        original = evidence["sources"][name]
        before, after = keyed(original, "source_sheet_row"), keyed(records, "source_sheet_row")
        columns = [c for c in original[0] if c != "source_sheet_row"] if original else []
        if any(any(c not in r for c in columns) for r in records):
            raise ValueError("Fresh source schema differs from checked KPI column contract")
        changed = sum(any(before[k][c] != after[k][c] for c in columns) for k in set(before) & set(after))
        new_keys, missing_keys = set(after) - set(before), set(before) - set(after)
        new_nonblank = sum(any(str(after[k][c] or "").strip() for c in columns) for k in new_keys)
        old_nonblank = sum(any(str(before[k][c] or "").strip() for c in columns) for k in missing_keys)
        results[tab] = {"status": "drift_detected" if changed or new_nonblank or old_nonblank else "no_kpi_input_drift",
                        "pinned_rows": len(before), "fresh_rows": len(after), "changed_existing_kpi_input_rows": changed,
                        "added_rows": len(new_keys), "absent_rows": len(missing_keys),
                        "added_nonblank_kpi_input_rows": new_nonblank, "absent_nonblank_kpi_input_rows": old_nonblank,
                        "fresh_extracted_at": item.get("metadata", {}).get("extracted_at")}
    return {"scope": "selected_KPI_input_columns_and_source_row_membership_only",
            "reporting_gold_repointed": False, "sources": results,
            "caveat": "Source row changes can include inserted/reordered rows. Absent rows are not confirmed deletions. This is a freshness comparison, not a fresh Gold KPI release."}


def validate(output_dir: str | Path, fresh_source_path: str | Path | None = None,
             *, project: str = PROJECT, location: str = LOCATION) -> dict:
    """Public API for a pipeline stage; no Google or warehouse mutation."""
    output = private_output(Path(output_dir))
    fresh = None
    if fresh_source_path is not None:
        path = Path(fresh_source_path).resolve()
        path.relative_to((ROOT / "outputs").resolve())
        fresh = json.loads(path.read_text(encoding="utf-8"))
    from google.cloud import bigquery
    client = bigquery.Client(project=project, location=location)
    try:
        if client.get_dataset(f"{project}.bronze").location.lower() != location.lower():
            raise ValueError("Warehouse region mismatch")
        summary, evidence = run_validation(Reader(client, project), datetime.now(MYT).date())
    finally:
        client.close()
    if fresh is not None:
        summary["fresh_source_comparison"] = fresh_source_drift(evidence, fresh)
    output.mkdir(parents=True)
    (output / "summary.json").write_text(json.dumps(primitive(summary), indent=2) + "\n", encoding="utf-8")
    (output / "private_source_evidence.json").write_text(json.dumps(primitive(evidence), indent=2) + "\n", encoding="utf-8")
    return {**summary, "summary_path": str(output / "summary.json"), "evidence_path": str(output / "private_source_evidence.json")}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--location", default=LOCATION)
    parser.add_argument("--fresh-source-json", type=Path, help="Optional private Sheets artifact for source freshness comparison")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "outputs/kpi_validation" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    args = parser.parse_args(argv)
    summary = validate(args.output_dir, args.fresh_source_json, project=args.project, location=args.location)
    print(json.dumps({"status": summary["status"], "checks": {name: result["status"] for name, result in summary["checks"].items()},
                      "query_count": summary["query_count"], "bytes_processed": summary["bytes_processed"], "output_dir": str(args.output_dir.resolve())}, indent=2))
    return 0 if summary["status"] == "pass_with_business_caveats" else 1


if __name__ == "__main__":
    raise SystemExit(main())
