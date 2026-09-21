"""Plan or run private Geoapify geocoding for historical Calendar visit addresses.

Default mode is read-only and sends no addresses. ``--execute`` sends at most
10 distinct, conservatively selected addresses to Geoapify and caches the
responses under the git-ignored data/processed directory. No source, Neon,
BigQuery, or weather writes occur. A geocoding result is not a verified visit.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import unicodedata

from dotenv import load_dotenv
from google.cloud import bigquery

from inspect_calendar_address_blocks import (
    ADDRESS_CUE,
    POSTCODE,
    address_block,
    clean_lines,
    normalized_candidate_key,
)
from inspect_weather_location_readiness import (
    LOCATION,
    MAX_BYTES,
    calendar_address_expr,
    calendar_source_table,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "processed" / "geocoding" / "geoapify_pilot_v17.jsonl"
API_URL = "https://api.geoapify.com/v1/geocode/search"
CONTACT = re.compile(
    r"(?:\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|https?://|\bwww\.|"
    r"(?:\+?60|0)[\s-]*1\d[\s-]*\d{3}[\s-]*\d{3,5}\b)", re.I
)
ADDRESS_START = re.compile(
    r"^(?:no(?:\.\s*|\s+)|lot\s+|[A-Z]?\d{1,4}[A-Z]?(?:[-/][A-Z0-9]+)*\b)", re.I
)
ADDRESS_ANYWHERE = re.compile(
    r"(?:\bno(?:\.\s*|\s+)|\blot\s+|(?<![A-Z0-9])[A-Z]?\d{1,4}[A-Z]?(?:[-/][A-Z0-9]+)+\b)", re.I
)
STREET_CUE = re.compile(
    r"\b(?:jalan|jln|taman|residensi|persiaran|lorong|road|street|kampung|kg\.?)\b", re.I
)
BARE_POSTCODE_START = re.compile(r"^\d{5}\b")
ADDRESS_LABEL = re.compile(
    r"(?i)(?:^|\s)\b(?:alamat|address(?:es)?|addres|full\s+address)\b\s*[:.]?\s*"
)
ADDRESS_PLACEHOLDER = re.compile(
    r"^(?:alamat\s+)?(?:tepat\s+)?akan\s+diberi\)?$", re.I
)
RESULT_TYPE_SCORE = {
    "building": 5, "amenity": 4, "street": 3, "suburb": 2,
    "district": 2, "postcode": 1, "city": 0,
}

# These words describe an address's structure, but are too common to establish
# that two Malaysian addresses refer to the same area.  They may support a
# match, but can never be the only matching evidence.
GENERIC_ADDRESS_TOKENS = {
    "address", "alamat", "bandar", "block", "blok", "city", "floor",
    "jalan", "kampung", "kg", "lorong", "malaysia", "no", "nombor",
    "persiaran", "precinct", "presint", "residence", "residensi", "road", "section",
    "street", "taman", "tingkat",
}
TOKEN_EXPANSIONS = {
    "bdr": ("bandar",),
    "buloh": ("buluh",),
    "condo": ("condominium",),
    "jln": ("jalan",),
    "like": ("loke",),
    "kembanagan": ("kembangan",),
    "kuatan": ("kuantan",),
    "plantium": ("platinum",),
    "reaidences": ("residence",),
    "residances": ("residence",),
    "residences": ("residence",),
    "seksyen": ("section",),
    "sel": ("selangor",),
    "sg": ("sungai",),
    "sri": ("seri",),
    "kl": ("kuala", "lumpur"),
    "kdh": ("kedah",),
    "sgr": ("selangor",),
}
ADMIN_AREA_TOKENS = {
    "ampang", "cyberjaya", "kajang", "kuala", "lumpur", "malaysia",
    "petaling", "putrajaya", "selangor", "sepang", "shah", "sungai",
}
ADDRESS_TOKEN = re.compile(r"[a-z0-9]+")
LEADING_PREMISE = re.compile(
    r"^\s*(?:no\.?\s*)?[a-z]?\d+[a-z]?(?:\s*[-/]\s*[a-z0-9]+){0,3}\s*,?\s*",
    re.I,
)
STRUCTURE_LABELS = {
    "blok": "block", "block": "block",
    "floor": "floor", "tingkat": "floor",
    "precinct": "precinct", "presint": "precinct", "section": "section",
}


def expanded_address_tokens(value: str | None) -> list[str]:
    normalized = unicodedata.normalize("NFKD", value or "").encode(
        "ascii", "ignore"
    ).decode("ascii").casefold()
    tokens: list[str] = []
    for token in ADDRESS_TOKEN.findall(normalized):
        tokens.extend(TOKEN_EXPANSIONS.get(token, (token,)))
    return tokens


def without_leading_premise(value: str) -> str:
    """Return a second-pass query without a leading house or unit identifier."""
    stripped = LEADING_PREMISE.sub("", value, count=1).strip(" ,;-")
    return stripped if stripped and stripped != value else value


def normalized_address_tokens(value: str | None) -> tuple[set[str], set[str]]:
    """Return distinctive words and non-postcode identifiers for comparison."""
    tokens = expanded_address_tokens(value)
    distinctive = {
        token for token in tokens
        if token not in GENERIC_ADDRESS_TOKENS
        and not token.isdigit()
        and len(token) >= 2
    }
    identifiers = {
        token for token in tokens
        if any(character.isdigit() for character in token)
        and not (len(token) == 5 and token.isdigit())
    }
    return distinctive, identifiers


def address_structure_values(value: str | None) -> dict[str, set[str]]:
    """Capture explicit section/precinct/block/floor identifiers."""
    tokens = expanded_address_tokens(value)
    values: dict[str, set[str]] = {}
    for index, token in enumerate(tokens[:-1]):
        label = STRUCTURE_LABELS.get(token)
        following = tokens[index + 1]
        if label and any(character.isdigit() for character in following):
            values.setdefault(label, set()).add(following)
    return values


def address_structure_conflicts(input_address: str | None,
                                provider_address: str | None) -> bool:
    input_structure = address_structure_values(input_address)
    provider_structure = address_structure_values(provider_address)
    return any(
        input_structure[label].isdisjoint(provider_structure[label])
        for label in input_structure.keys() & provider_structure.keys()
    )


def address_text_agreement(input_address: str | None,
                           provider_address: str | None) -> bool:
    """Conservatively identify meaningful agreement between two addresses.

    Generic words (for example ``Jalan``, ``Taman`` or ``Presint``) do not
    count.  A match needs distinctive place/street wording, with either broad
    coverage of the input or a shared unit/street identifier.
    """
    input_words, input_ids = normalized_address_tokens(input_address)
    provider_words, provider_ids = normalized_address_tokens(provider_address)
    if address_structure_conflicts(input_address, provider_address):
        return False
    if not input_words or not provider_words:
        return False
    shared_words = input_words & provider_words
    if not shared_words:
        return False
    coverage = len(shared_words) / len(input_words)
    if len(input_words) == 1:
        return len(shared_words) == 1
    if (len(shared_words) == 1
            and len(next(iter(shared_words))) >= 8
            and next(iter(shared_words)) not in ADMIN_AREA_TOKENS
            and min(len(input_words), len(provider_words)) <= 3):
        # A long shared proper-name token (for example ``Gardenview``) can
        # identify a named building even when one provider returns only the
        # development name and the other retains nearby street wording.
        return True
    if len(shared_words) >= 3:
        return True
    if (len(shared_words) >= 2
            and sum(len(word) for word in shared_words) >= 10
            and not (shared_words & ADMIN_AREA_TOKENS)):
        # A two-word distinctive property name (for example ``Glomac Centro``)
        # remains strong identity evidence even when the input also contains
        # unit and locality words that the provider omits.
        return True
    if len(shared_words) >= 2 and coverage >= 0.4:
        return True
    return coverage >= 0.35 and bool(input_ids & provider_ids)


class GeoapifyRequestError(RuntimeError):
    """A single provider request failed and must not reveal its address."""


def eligible_address(block: str | None) -> bool:
    """Prefer clear premise/street strings; never transmit contact-bearing text."""
    if not block:
        return False
    text = " ".join(block.split())
    return (15 <= len(text) <= 160 and not BARE_POSTCODE_START.search(text)
            and bool(ADDRESS_START.search(text) or STREET_CUE.match(text))
            and bool(ADDRESS_CUE.search(text)) and not CONTACT.search(text))


def sanitized_address_candidate(block: str | None) -> str | None:
    """Remove labels/contact tails and return only a plausible address substring."""
    if not block:
        return None
    # Calendar exports contain both real HTML and HTML-escaped markup. Decode
    # and flatten it before locating fields so ``&lt;br&gt;Package:`` is treated
    # as a following form field rather than part of the address sent upstream.
    text = " ".join(" ".join(clean_lines(block)).split())
    label = ADDRESS_LABEL.search(text)
    explicitly_labelled = label is not None
    if label:
        text = text[label.end():]
    text = re.sub(
        r"(?i)\s+(?:package|problem|invoice(?:\s*id)?|emel|e-?mail|phone(?:\s*no)?|treatment)\s*:.*$",
        "", text,
    ).strip(" ,;-")
    text = re.sub(
        r"(?i)\s*\(\s*alamat\s+tepat\s+akan\s+diberi\s*\)\s*$", "", text
    ).strip(" ,;-")
    contact = CONTACT.search(text)
    if contact:
        text = text[:contact.start()].strip(" ,;-")
    if not text:
        return None
    # Preserve a complete address that already begins with a premise number.
    # Looking for another number first used to turn e.g. ``16, Jalan ... 7/2L``
    # into ``7/2L ...`` and then reject it for losing the street cue.
    if (not explicitly_labelled and not ADDRESS_START.search(text)
            and not STREET_CUE.match(text)):
        start = ADDRESS_ANYWHERE.search(text)
        if start:
            text = text[start.start():]
        elif (street := STREET_CUE.search(text)):
            text = text[street.start():]
    text = " ".join(text.split()).strip(" ,;-")
    if explicitly_labelled:
        # An explicit address label is stronger evidence than a particular
        # Malaysian spelling convention. This safely covers named premises,
        # unit-led addresses and common free-text variations after contact
        # and following form fields have already been removed.
        return text if 8 <= len(text) <= 160 and not BARE_POSTCODE_START.search(text) else None
    return text if eligible_address(text) else None


def fetch_candidates(start_date: date, end_date: date) -> dict[str, dict]:
    if start_date > end_date:
        raise ValueError("start_date must not be after end_date")
    source = calendar_source_table()
    sql = f"""
    with events as (
        select e.calendar_event_row, b.description, b.location,
            regexp_replace(regexp_replace(coalesce(b.description, ''),
                r'(?i)</?(?:p|div|li|br)\\b[^>]*>', '\\n'),
                r'<[^>]+>', '') as description_text
        from `profound-keel-500007-s4.silver.calendar_events` e
        join {source} b using (calendar_event_row)
        where e.service_candidate
          and e.event_date_local between date '{start_date.isoformat()}'
              and date '{end_date.isoformat()}'
    )
    select calendar_event_row, description, description_text, location,
        {calendar_address_expr('description_text')} as extracted_line
    from events order by calendar_event_row
    """
    client = bigquery.Client(project="profound-keel-500007-s4", location=LOCATION)
    try:
        dry = client.query(sql, job_config=bigquery.QueryJobConfig(
            dry_run=True, use_query_cache=False), location=LOCATION)
        if dry.total_bytes_processed > MAX_BYTES:
            raise SystemExit("Calendar address query exceeds the 100 MiB cap")
        rows = client.query(sql, job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES), location=LOCATION).result()
        by_hash: dict[str, dict] = {}
        seen_rows: set[int] = set()
        for row in rows:
            if row.calendar_event_row in seen_rows:
                raise SystemExit("Calendar event grain expanded; no geocoding performed")
            seen_rows.add(row.calendar_event_row)
            block, _ = address_block(row.description, row.extracted_line)
            address = sanitized_address_candidate(block)
            # “alamat tepat akan diberi” means the exact address will be
            # supplied later. It is a status note, not a geocodable location.
            # If an upstream extraction isolates only that parenthetical note,
            # retry against the complete labelled description.
            if address and ADDRESS_PLACEHOLDER.fullmatch(address.strip()):
                address = None
            address = (
                address
                or sanitized_address_candidate(row.location)
                or sanitized_address_candidate(row.description_text)
            )
            if not address:
                continue
            key = hashlib.sha256(normalized_candidate_key(address).encode()).hexdigest()
            candidate = by_hash.setdefault(key, {"address": address, "event_rows": []})
            candidate["event_rows"].append(row.calendar_event_row)
        print(f"Service-like Calendar rows checked ({start_date} through {end_date}): {len(seen_rows)}")
        print(f"Conservative distinct address candidates: {len(by_hash)}")
        print("No customer names, phones, emails, or descriptions printed.")
        return by_hash
    finally:
        client.close()


def cached_hashes() -> set[str]:
    if not OUTPUT.exists():
        return set()
    hashes: set[str] = set()
    for line in OUTPUT.read_text(encoding="utf-8").splitlines():
        if line.strip():
            hashes.add(json.loads(line)["address_hash"])
    return hashes


def choose_result(address: str, results: list[dict]) -> tuple[dict | None, bool | None]:
    """Prefer semantic address agreement, then postcode and provider quality."""
    input_match = POSTCODE.search(address)
    input_postcode = input_match.group(0) if input_match else None
    if not results:
        return None, None
    def score(item: dict) -> tuple:
        postcode_agrees = bool(input_postcode and item.get("postcode") == input_postcode)
        rank = item.get("rank") or {}
        input_words, input_ids = normalized_address_tokens(address)
        provider_words, provider_ids = normalized_address_tokens(item.get("formatted"))
        shared_words = input_words & provider_words
        coverage = len(shared_words) / len(input_words) if input_words else 0
        structure_conflict = address_structure_conflicts(address, item.get("formatted"))
        return (
            not structure_conflict,
            address_text_agreement(address, item.get("formatted")),
            postcode_agrees,
            len(shared_words), coverage,
            len(input_ids & provider_ids),
            RESULT_TYPE_SCORE.get(item.get("result_type"), -1),
            float(rank.get("confidence") or 0),
        )
    selected = max(results, key=score)
    agrees = None if input_postcode is None else selected.get("postcode") == input_postcode
    return selected, agrees


def precision_tier(result_type: str | None, postcode_agrees: bool | None,
                   confidence: float | None) -> str:
    if result_type == "building" and postcode_agrees is not False and (confidence or 0) >= 0.7:
        return "precise_candidate"
    if result_type in {"building", "amenity", "street"} and postcode_agrees is True:
        return "street_candidate"
    if (result_type in {"building", "amenity", "street"}
            and postcode_agrees is None and (confidence or 0) >= 0.5):
        return "street_candidate"
    if postcode_agrees is True:
        return "postcode_area_candidate"
    return "manual_review"


def analysis_tier(record: dict) -> str:
    """Classify suitability for area-level weather/heatmap analysis.

    This does not promote a candidate to an exact service property. Geoapify
    building, amenity, and street results can still support coarse spatial
    analysis when a postcode was not supplied, provided coordinates exist and
    the provider matched at the corresponding address level.
    """
    text_agrees = address_text_agreement(
        record.get("input_address"), record.get("formatted")
    )
    has_coordinates = record.get("latitude") is not None and record.get("longitude") is not None
    if has_coordinates and record.get("coordinate_source") == "manual_user_verified":
        return "manual_verified"
    if has_coordinates and record.get("coordinate_source") == "external_area_reference":
        return "area_reference_verified"
    if has_coordinates and record.get("peer_address_agreement") is True:
        return "peer_address_candidate"
    reference_distance = record.get("postcode_reference_distance_km")
    if (record.get("postcode_agrees") is False
            and reference_distance is not None
            and float(reference_distance) > 10):
        return "manual_review"
    if (has_coordinates and record.get("google_places_hint_agreement") is True
            and record.get("postcode_agrees") is not False and not text_agrees):
        # A transient Google locality hint may support broad weather-area use,
        # but neither provider proximity nor a Google hint is address-match
        # evidence. Meaningful input/Geoapify text agreement uses the ordinary
        # provider rules below.
        return "google_hinted_area_candidate"
    base = precision_tier(
        record.get("result_type"), record.get("postcode_agrees"),
        record.get("confidence"),
    )
    # A provider confidence score is not evidence that the returned street is
    # the street the user supplied.  For inputs without a postcode, require
    # meaningful text agreement before retaining street-level acceptance.
    if (base == "street_candidate" and record.get("postcode_agrees") is None
            and not text_agrees):
        base = "manual_review"
    if base != "manual_review":
        return base
    if (has_coordinates and record.get("postcode_agrees") is False
            and reference_distance is not None
            and float(reference_distance) <= 5):
        return "proximity_candidate"
    area_match_types = {"full_match", "inner_part", "match_by_building", "match_by_street"}
    if (has_coordinates and text_agrees and record.get("postcode_agrees") is None
            and record.get("result_type") in {"building", "amenity", "street"}
            and record.get("match_type") in area_match_types):
        return "area_analysis_candidate"
    input_words, _ = normalized_address_tokens(record.get("input_address"))
    provider_words, _ = normalized_address_tokens(record.get("formatted"))
    shared_words = input_words & provider_words
    if (has_coordinates and len(shared_words) >= 2
            and record.get("result_type") in {"building", "amenity", "street"}
            and not address_structure_conflicts(
                record.get("input_address"), record.get("formatted"))):
        return "text_agreement_candidate"
    if has_coordinates and text_agrees:
        return "text_agreement_candidate"
    return "manual_review"


def geocode(address: str, key: str, limit: int = 5) -> dict:
    params = urllib.parse.urlencode({
        "text": f"{address}, Malaysia", "filter": "countrycode:my", "limit": limit,
        "lang": "en", "format": "json", "apiKey": key,
    })
    request = urllib.request.Request(f"{API_URL}?{params}", headers={
        "Accept": "application/json", "User-Agent": "nomobug-capstone-geocode-pilot/1.0",
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.load(response)
    except urllib.error.HTTPError as exc:
        raise GeoapifyRequestError(f"HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError, ValueError):
        raise GeoapifyRequestError("network_or_response_error") from None
    results = data.get("results", [])
    if not isinstance(results, list):
        raise GeoapifyRequestError("unexpected_response")
    selected, postcode_agrees = choose_result(address, results)
    if selected is None:
        return {"result_count": 0}
    top = selected
    rank = top.get("rank") or {}
    confidence = rank.get("confidence")
    return {
        "result_count": len(results),
        "latitude": top.get("lat"), "longitude": top.get("lon"),
        "result_type": top.get("result_type"),
        "confidence": confidence,
        "match_type": rank.get("match_type"),
        "formatted": top.get("formatted"),
        "postcode": top.get("postcode"),
        "postcode_agrees": postcode_agrees,
        "precision_tier": precision_tier(top.get("result_type"), postcode_agrees, confidence),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true",
                        help="Send a capped pilot to Geoapify using a configured key")
    parser.add_argument("--max-new-requests", type=int, default=5)
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2023, 1, 1))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 12, 31))
    args = parser.parse_args()
    if not 1 <= args.max_new_requests <= 600:
        raise SystemExit("Request cap must be between 1 and 600")
    if not 1 <= args.workers <= 3:
        raise SystemExit("Worker count must be between 1 and 3")
    candidates = fetch_candidates(args.start_date, args.end_date)
    cached = cached_hashes()
    pending = [(key, item) for key, item in sorted(candidates.items()) if key not in cached]
    print(f"Already cached: {len(cached)}; eligible pending: {len(pending)}")
    print(f"Pilot would send at most {min(len(pending), args.max_new_requests)} unique addresses")
    if not args.execute:
        print("PLAN ONLY: no Geoapify calls or file writes.")
        return
    load_dotenv(ROOT / ".env")
    api_key = os.getenv("NOMOBUG_GEOAPIFY_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Missing NOMOBUG_GEOAPIFY_API_KEY in private .env or environment; no calls made")
    if not pending:
        print("Nothing new to geocode.")
        return
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    attempted = 0
    failed = 0
    failure_reasons: Counter[str] = Counter()
    selected = pending[:args.max_new_requests]
    with OUTPUT.open("a", encoding="utf-8") as handle, ThreadPoolExecutor(max_workers=args.workers) as pool:
        for batch_start in range(0, len(selected), 30):
            futures = {}
            for address_hash, item in selected[batch_start:batch_start + 30]:
                futures[pool.submit(geocode, item["address"], api_key)] = (address_hash, item)
                time.sleep(0.26)  # Submit fewer than 4 requests/second.
            for future in as_completed(futures):
                address_hash, item = futures[future]
                try:
                    result = future.result()
                except GeoapifyRequestError as exc:
                    failed += 1
                    failure_reasons[str(exc)] += 1
                    continue
                attempted += 1
                record = {
                    "provider": "geoapify", "geocoded_at_utc": datetime.now(timezone.utc).isoformat(),
                    "address_hash": address_hash, "input_address": item["address"],
                    "calendar_event_rows": item["event_rows"], **result,
                }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
    print(f"Successful new Geoapify results: {attempted}; cached in private {OUTPUT.relative_to(ROOT)}")
    print(f"Individual failures left uncached for later review/retry: {failed}")
    if failure_reasons:
        safe_summary = ", ".join(
            f"{reason}={count}" for reason, count in sorted(failure_reasons.items())
        )
        print(f"Failure categories (no address values): {safe_summary}")
    print("Coordinates are candidates, not verified service points; no warehouse/weather writes.")


if __name__ == "__main__":
    main()
