#!/usr/bin/env python3
"""Run every bundled synthetic scenario and verify the JSON contract."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from analytics_engine.cli import _load_scenario, _validate_schema  # noqa: E402
from analytics_engine import run_analysis  # noqa: E402


def main() -> int:
    samples = ROOT / "data" / "samples"
    scenarios = ("retail", "service", "cold_start", "messy")
    failed = False
    print("BizIQ synthetic-scenario verification")
    print("=" * 42)
    for name in scenarios:
        business, data = _load_scenario(samples, name)
        result = run_analysis(business, data)
        # Enforce strict JSON serialization, including rejection of NaN/Infinity.
        json.dumps(result, allow_nan=False)
        errors = _validate_schema(result, ROOT / "contracts" / "analysis-result.schema.json")
        ok = not errors and result.get("status") != "failed"
        print(f"{'PASS' if ok else 'FAIL'}  {name:12} status={result.get('status'):9} "
              f"evidence={result.get('evidence_level')}")
        for error in errors:
            print(f"      schema: {error}")
        failed |= not ok
    print("=" * 42)
    print("All sample scenarios passed." if not failed else "One or more scenarios failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
