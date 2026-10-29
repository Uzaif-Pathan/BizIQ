#!/usr/bin/env python3
"""Load the ASUSE 2025 benchmark file into the database.

    cd <repo root>
    python scripts/load_benchmarks.py            # load (skips if already loaded)
    python scripts/load_benchmarks.py --reload   # delete the old rows of this source and load again

Rows the source reports as zero are skipped (the source says to treat them as "not available").
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

from sqlalchemy import delete, select  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models import BenchmarkSource, IndustryBenchmark  # noqa: E402
from app.services.benchmark_loader import SOURCE, rows_from_csv  # noqa: E402

CSV = ROOT / "database" / "reference_data" / "biziq_asuse_2025_benchmark.csv"


def load(db, reload: bool = False) -> str:
    rows, counts = rows_from_csv(CSV)
    source = db.scalar(select(BenchmarkSource).where(BenchmarkSource.source_name == SOURCE["source_name"]))
    if source is not None and not reload:
        return "already loaded (use --reload to replace)"
    if source is None:
        source = BenchmarkSource(**SOURCE)
        db.add(source)
        db.flush()
    else:
        db.execute(delete(IndustryBenchmark).where(IndustryBenchmark.source_id == source.source_id))
    db.bulk_insert_mappings(IndustryBenchmark, [{**r, "source_id": source.source_id} for r in rows])
    db.commit()
    return f"loaded {counts['rows_loaded']} rows (skipped {counts['skipped_zero_reported']} zero-reported)"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()
    if not get_settings().database_url:
        print("DATABASE_URL is not set.")
        return 1
    with SessionLocal() as db:
        print(load(db, args.reload))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
