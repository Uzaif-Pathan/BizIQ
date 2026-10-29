"""Reads the ASUSE 2025 benchmark CSV into rows for `industry_benchmarks` (no database needed here).

Rows reported as zero by the source are skipped: the source marks them "treat as not available, not as
a real zero", so loading them would create fake zero benchmarks.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

SOURCE = {
    "source_name": "ASUSE 2025 (Jan-Dec 2025)",
    "publisher": "MoSPI (eSankhyiki)",
    "source_type": "SURVEY",
    "source_url": None,
    "reference_year": 2025,
}
REQUIRED = ["geography", "geo_level", "sector", "industry", "industry_scheme", "establishment_type",
            "metric", "worker_group", "value", "unit", "is_rollup", "note"]


def rows_from_csv(path: Path) -> tuple[List[Dict[str, Any]], Dict[str, int]]:
    """Return (rows ready to insert, counts). Raises ValueError when the file lacks expected columns."""
    df = pd.read_csv(path)
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Benchmark file is missing columns: {', '.join(missing)}")
    total = len(df)
    value = pd.to_numeric(df["value"], errors="coerce")
    note = df["note"].fillna("").astype(str)
    zero_reported = (value == 0) & note.str.startswith("Zero reported")
    unusable = value.isna() | zero_reported
    today = date.today()
    rows: List[Dict[str, Any]] = []
    for r, v in zip(df[~unusable].itertuples(index=False), value[~unusable]):
        national = r.geo_level == "All India"
        rows.append({
            "industry_name": r.industry, "metric_name": r.metric, "metric_value": float(v), "metric_unit": r.unit,
            "geography_level": "NATIONAL" if national else "STATE", "country": "India",
            "state": None if national else r.geography, "district": None,
            "reference_year": SOURCE["reference_year"], "last_updated": today,
            "confidence_note": (r.note if isinstance(r.note, str) and r.note else None),
            "sector": r.sector, "establishment_type": r.establishment_type, "worker_group": r.worker_group,
            "industry_scheme": r.industry_scheme, "is_rollup": bool(r.is_rollup),
        })
    return rows, {"rows_in_file": total, "rows_loaded": len(rows), "skipped_zero_reported": int(zero_reported.sum()),
                  "skipped_unusable": int((unusable & ~zero_reported).sum())}
