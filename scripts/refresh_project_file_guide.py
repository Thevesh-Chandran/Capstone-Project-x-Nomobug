"""Refresh navigation and inventory without executing notebooks or changing evidence.

Use --clean-caches to remove only regenerable caches outside protected folders.
"""

import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import shutil
import stat
from string import Template

ROOT = Path(__file__).resolve().parents[1]
CACHES = {"__pycache__", ".pytest_cache", ".ruff_cache", ".ipynb_checkpoints"}
PROTECTED = {
    ".git",
    ".venv",
    "secrets",
    "data",
    "outputs",
    "archive",
    "tmp",
    ".codex-tmp",
    ".codex-qa",
}
AREAS = {
    "notebooks": "Analysis notebooks",
    "scripts": "Processing and model code",
    "dbt": "Warehouse SQL",
    "webapp": "Website",
    "config": "Rules and protocols",
    "tests": "Tests",
    "infra": "Hosting",
    "planning": "Specifications and dated records",
    "docs": "Report documents",
    "outputs": "Results and evidence",
    "data": "Private data",
    "archive": "Retired material",
    "project_guide": "File guides",
    "templates": "Templates",
    ".github": "Automation",
}


def walk(base, skip=()):
    for parent, dirs, files in os.walk(base, followlinks=False):
        dirs[:] = [
            d for d in dirs if d not in skip and not (Path(parent) / d).is_symlink()
        ]
        for name in files:
            p = Path(parent) / name
            if not p.is_symlink():
                yield p


def describe(p):
    fallback = p.stem.replace("_", " ").replace("-", " ")
    if p.suffix not in {".py", ".md"}:
        return fallback
    try:
        text = p.read_text(encoding="utf-8-sig")
        if p.suffix == ".py":
            return (ast.get_docstring(ast.parse(text)) or fallback).splitlines()[0]
        if p.suffix == ".md":
            return next(
                (s[2:] for s in text.splitlines() if s.startswith("# ")), fallback
            )
    except (OSError, UnicodeError, SyntaxError):
        pass
    return fallback


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean-caches", action="store_true")
    args = parser.parse_args()
    removed = []
    if args.clean_caches:
        for parent, dirs, _ in os.walk(ROOT, followlinks=False):
            for name in list(dirs):
                p = Path(parent) / name
                if (
                    name in PROTECTED
                    or p.is_symlink()
                    or ("dbt" in p.parts and name in {"target", "logs", "dbt_packages"})
                ):
                    dirs.remove(name)
                elif name in CACHES:
                    dirs.remove(name)
                    resolved = p.resolve()
                    if (
                        not resolved.is_relative_to(ROOT.resolve())
                        or resolved.name not in CACHES
                    ):
                        raise ValueError("Invalid cleanup target")
                    removed.append(
                        {
                            "path": p.relative_to(ROOT).as_posix(),
                            "bytes": sum(f.stat().st_size for f in walk(p)),
                        }
                    )

                    def clear_readonly(function, filename, error):
                        Path(filename).chmod(stat.S_IWRITE | stat.S_IREAD)
                        function(filename)

                    shutil.rmtree(resolved, onexc=clear_readonly)
    sizes = []
    for p in sorted(ROOT.iterdir()):
        if p.name in {".git", "secrets", ".env"}:
            continue
        fs = list(walk(p)) if p.is_dir() else [p]
        sizes.append(
            {
                "Folder": p.name,
                "Files": len(fs),
                "Bytes": sum(f.stat().st_size for f in fs),
            }
        )
    rows = []
    hashes = {}
    for folder, label in AREAS.items():
        if folder in {"outputs", "data", "docs", "archive"}:
            continue
        for p in sorted(
            walk(ROOT / folder, CACHES | {"target", "logs", "dbt_packages"})
        ):
            if "evidence" in p.parts or p.suffix.lower() not in {
                ".py",
                ".sql",
                ".md",
                ".yaml",
                ".yml",
                ".json",
                ".ps1",
                ".js",
                ".css",
                ".html",
                ".ipynb",
                ".txt",
            }:
                continue
            rows.append(
                {
                    "Area": label,
                    "File": p.relative_to(ROOT).as_posix(),
                    "Purpose": describe(p),
                }
            )
            if folder == "scripts" and p.suffix == ".py" and p.stat().st_size:
                hashes.setdefault(
                    hashlib.sha256(p.read_bytes()).hexdigest(), []
                ).append(p.relative_to(ROOT).as_posix())
    guide = ROOT / "project_guide"
    for name, records in [("File_Catalogue.csv", rows), ("Folder_Sizes.csv", sizes)]:
        with (guide / name).open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    e = html.escape
    cards = "".join(
        f'<a class="card" href="{e(folder)}/"><b>{e(label)}</b><code>{e(folder)}/</code></a>'
        for folder, label in AREAS.items()
    )
    books = "".join(
        f'<li><a href="{p.relative_to(ROOT).as_posix()}">{e(p.stem.replace("_", " "))}</a> · <a href="{p.with_suffix(".ipynb").relative_to(ROOT).as_posix()}">Jupyter</a></li>'
        for p in sorted((ROOT / "notebooks").glob("[0-9][0-9]_*.html"))
    )
    table = "".join(
        f'<tr><td>{e(r["Area"])}</td><td><a href="{e(r["File"])}">{e(r["File"])}</a></td><td>{e(r["Purpose"])}</td></tr>'
        for r in rows
    )
    template_path = ROOT / "templates" / "project_file_guide.html"
    template = Template(template_path.read_text(encoding="utf-8"))
    areas = sorted({row["Area"] for row in rows})
    page = template.substitute(
        folder_cards=cards,
        notebooks=books,
        file_rows=table,
        area_options="".join(f"<option>{e(area)}</option>" for area in areas),
    )
    (ROOT / "FILE_GUIDE.html").write_text(page, encoding="utf-8")
    report = {
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "removed_caches": removed,
        "removed_bytes": sum(r["bytes"] for r in removed),
        "folders": sizes,
        "identical_nonempty_scripts": [v for v in hashes.values() if len(v) > 1],
        "catalogued_files": len(rows),
        "protected": "Source, data, models, protocols, receipts, dbt target and cloud resources unchanged.",
    }
    audit = ROOT / "outputs/project_audit/20261102_folder_cleanup"
    audit.mkdir(parents=True, exist_ok=True)
    (
        audit / ("cleanup_" + datetime.now(timezone.utc).strftime("%H%M%S") + ".json")
    ).write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {k: v for k, v in report.items() if k not in {"folders", "removed_caches"}},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
