"""Clean the raw CSV, build data/analytics.duckdb, run checks, export SQL results.

Usage:  python pipeline.py
Exit codes: 0 ok, 2 missing raw data, 3 database locked, 4 integrity check failed.
"""
from __future__ import annotations

import hashlib
import importlib.metadata as md
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from src.clean_data import clean, read_raw
from src.config import (DATABASE_PATH, DOWNLOAD_URL, OUTPUTS_DIR, PROCESSED_DIR, PROJECT_ROOT,
                        RAW_CSV, SOURCE_URL)
from src.database import DatabaseLockedError, IntegrityCheckError, build_database, connect_read_only
from src.queries import build_info, default_params, export_all
from src.validate import check_clean_reconciliation


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def package_versions() -> dict:
    out = {"python": platform.python_version()}
    for p in ["pandas", "duckdb", "streamlit", "plotly", "pytest"]:
        try:
            out[p] = md.version(p)
        except md.PackageNotFoundError:
            out[p] = "not installed"
    return out


def run(raw_path: Path = RAW_CSV, db_path: Path = DATABASE_PATH,
        outputs_dir: Path = OUTPUTS_DIR, processed_dir: Path = PROCESSED_DIR) -> dict:
    raw_path, db_path = Path(raw_path), Path(db_path)
    outputs_dir, processed_dir = Path(outputs_dir), Path(processed_dir)
    if not raw_path.exists():
        raise FileNotFoundError(
            f"Raw data not found: {raw_path}\n"
            f"Download the dataset from {SOURCE_URL}\n"
            f"(direct: {DOWNLOAD_URL}) and extract ecommerce_returns_synthetic_data.csv into data/raw/.")

    dataset_sha = sha256_of(raw_path)
    print(f"[1/5] Cleaning {raw_path.name} (sha256 {dataset_sha[:12]}...)")
    result = clean(read_raw(raw_path))
    check_clean_reconciliation(result.summary)

    processed_dir.mkdir(parents=True, exist_ok=True)
    outputs_dir.mkdir(parents=True, exist_ok=True)
    result.orders.to_csv(processed_dir / "orders_clean.csv", index=False)
    result.returns.to_csv(processed_dir / "returns_clean.csv", index=False)
    result.issues.to_csv(outputs_dir / "issue_report.csv", index=False)

    built_at = datetime.now(timezone.utc).replace(microsecond=0)
    build_id = f"{built_at:%Y%m%dT%H%M%SZ}-{dataset_sha[:12]}"
    try:
        rel_raw = raw_path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        rel_raw = raw_path.name
    meta = {"build_id": build_id, "built_at": built_at.replace(tzinfo=None),
            "dataset_sha256": dataset_sha, "raw_file": rel_raw, "source_rows": len(result.orders)
            + int((result.issues["disposition"] == "excluded").sum())}

    print(f"[2/5] Building {db_path.name} in one transaction")
    checks = build_database(result.orders, result.returns, db_path, meta)
    print(f"[3/5] Integrity checks: {int(checks['passed'].sum())}/{len(checks)} passed")

    quality = pd.concat([
        result.summary,
        pd.DataFrame({"section": "sql_checks", "metric": checks["check_name"],
                      "value": checks["passed"].map({True: "pass", False: "fail"}),
                      "note": "observed=" + checks["observed"].astype(str)
                              + " expected=" + checks["expected"].astype(str)}),
    ], ignore_index=True)
    quality.to_csv(outputs_dir / "data_quality_report.csv", index=False)

    print("[4/5] Exporting SQL analysis results")
    con = connect_read_only(db_path)
    try:
        params = default_params(con)
        exports = export_all(con, outputs_dir / "query_results", params)
        info = build_info(con)
        overview = con.execute(
            "SELECT count(*) FILTER (WHERE is_rate_eligible), "
            "count(*) FILTER (WHERE is_rate_eligible AND is_returned) FROM analytics_orders").fetchone()
    finally:
        con.close()

    excluded_by_reason = (result.issues[result.issues["disposition"] == "excluded"]["issue_code"]
                          .value_counts().to_dict())
    metadata = {
        "build_id": info["build_id"],
        "built_at_utc": built_at.isoformat(),
        "dataset": {"source_url": SOURCE_URL, "raw_file": rel_raw, "sha256": dataset_sha},
        "counts": {
            "source_rows": meta["source_rows"],
            "excluded_rows": int(sum(excluded_by_reason.values())),
            "excluded_by_primary_reason": {k: int(v) for k, v in excluded_by_reason.items()},
            "retained_orders": len(result.orders),
            "returns_rows": len(result.returns),
            "eligible_purchases": int(overview[0]),
            "returned_purchases": int(overview[1]),
        },
        "integrity_checks": {r.check_name: bool(r.passed) for r in checks.itertuples()},
        "export_filters": {"start_date": str(params["start_date"]), "end_date": str(params["end_date"]),
                           "categories": params["categories"], "min_support": params["min_support"]},
        "exports": exports,
        "package_versions": package_versions(),
    }
    (outputs_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"[5/5] Done. build_id={info['build_id']} eligible={overview[0]} returned={overview[1]}")
    return metadata


def main() -> int:
    try:
        run()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except DatabaseLockedError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3
    except IntegrityCheckError as exc:
        print(f"ERROR: {exc}\nThe database was rolled back; previous contents are unchanged.", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
