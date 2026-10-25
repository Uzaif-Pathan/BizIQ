"""Command-line demo for the standalone BizIQ analytics engine.

Run from the repository root:
    python scripts/run_demo.py --scenario retail
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from .pipeline import run_analysis


def _load_scenario(samples_dir: Path, scenario: str) -> tuple[dict[str, Any], dict[str, pd.DataFrame]]:
    business_file = samples_dir / "businesses.json"
    if not business_file.exists():
        raise FileNotFoundError(f"Business registry not found: {business_file}")
    businesses = json.loads(business_file.read_text(encoding="utf-8"))
    if scenario not in businesses:
        available = ", ".join(sorted(businesses))
        raise ValueError(f"Unknown scenario {scenario!r}. Choose one of: {available}")

    business = businesses[scenario]
    scenario_dir = samples_dir / scenario
    data: dict[str, pd.DataFrame] = {}
    for table in ("financials", "customers", "products"):
        path = scenario_dir / f"{table}.csv"
        if path.exists():
            data[table] = pd.read_csv(path)
    if not data:
        raise FileNotFoundError(f"No CSV datasets found in {scenario_dir}")
    return business, data


def _validate_schema(result: dict[str, Any], schema_path: Path) -> list[str]:
    """Validate output if jsonschema is installed; return human-readable errors."""
    try:
        import jsonschema
    except ImportError:
        return ["Schema validation skipped: install jsonschema to enable it."]
    if not schema_path.exists():
        return [f"Schema file not found: {schema_path}"]
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    return [f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
            for e in sorted(validator.iter_errors(result), key=lambda e: list(map(str, e.absolute_path)))]


def _render_summary(result: dict[str, Any], business: dict[str, Any]) -> str:
    """Render a compact, readable summary for a live classroom demonstration."""
    lines = [
        f"BizIQ analysis — {business.get('name') or business.get('business_id', 'Business')}",
        "=" * 64,
        f"Status: {result.get('status')} | Evidence: {result.get('evidence_level')} | "
        f"Benchmark: {result.get('benchmark_status')}",
    ]
    metrics = result.get("metrics") or {}
    lines.append("\nKey metrics")
    preferred = (
        "revenue", "expenses", "profit", "profit_margin_pct", "revenue_mom_pct",
        "revenue_yoy_pct", "active_customers", "avg_transaction_value",
        "gross_margin_pct", "units_sold",
    )
    labels = {
        "revenue": "Revenue", "expenses": "Expenses", "profit": "Profit",
        "profit_margin_pct": "Profit margin", "revenue_mom_pct": "Revenue MoM",
        "revenue_yoy_pct": "Revenue YoY", "active_customers": "Active customers",
        "avg_transaction_value": "Average transaction", "gross_margin_pct": "Gross margin",
        "units_sold": "Units sold",
    }
    shown = 0
    for key in preferred:
        item = metrics.get(key)
        if not isinstance(item, dict):
            continue
        value = item.get("value")
        if value is None:
            continue
        unit = item.get("unit", "")
        if unit == "INR":
            formatted = f"₹{value:,.2f}"
        elif unit == "percent":
            formatted = f"{value:.2f}%"
        else:
            formatted = f"{value:,.2f}" if isinstance(value, (int, float)) else str(value)
        period = f" ({item['period']})" if item.get("period") else ""
        lines.append(f"  • {labels.get(key, key)}: {formatted}{period}")
        shown += 1
    if shown == 0:
        lines.append("  No headline metrics are available from the supplied data.")

    health = result.get("health_score") or {}
    lines.append("\nBusiness health")
    if health.get("score") is None:
        lines.append("  Score unavailable — not enough suitable indicators.")
    else:
        lines.append(f"  Score: {health['score']:.1f}/100 (rule-based indicator, not a success probability)")

    findings = result.get("findings") or []
    lines.append(f"\nFindings ({len(findings)})")
    for finding in findings[:3]:
        evidence = finding.get("evidence") or finding.get("summary") or finding.get("type", "Finding")
        lines.append(f"  • [{finding.get('severity', 'info')}] {evidence}")
    if not findings:
        lines.append("  No supported findings were generated.")

    recommendations = result.get("recommendations") or []
    lines.append(f"\nRecommended next actions ({len(recommendations)})")
    for recommendation in recommendations[:3]:
        lines.append(f"  • [{recommendation.get('priority', 'medium')}] "
                     f"{recommendation.get('issue', 'Review business finding')}")
        if recommendation.get("action"):
            lines.append(f"      Action: {recommendation['action']}")
    if not recommendations:
        lines.append("  No recommendations were generated from the available evidence.")

    models = result.get("models") or {}
    lines.append("\nModels")
    for key in ("segmentation", "forecast"):
        model = models.get(key) or {"status": "not_applicable"}
        lines.append(f"  • {key}: {model.get('status', 'not_applicable')}")
    warnings = (result.get("validation") or {}).get("warnings") or []
    errors = (result.get("validation") or {}).get("errors") or []
    lines.append(f"\nData quality: {len(errors)} error(s), {len(warnings)} warning(s)")
    for issue in (errors + warnings)[:3]:
        lines.append(f"  • {issue.get('code', 'issue')}: {issue.get('message', '')}")
    lines.append("\nNote: Recommendations are decision support, not guarantees. Verify source data and context.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the BizIQ analytics engine on synthetic sample data.")
    parser.add_argument("--scenario", default="retail",
                        help="Sample scenario: retail, service, cold_start, or messy (default: retail)")
    parser.add_argument("--samples-dir", type=Path, default=None,
                        help="Directory containing businesses.json and scenario folders")
    parser.add_argument("--output", type=Path, default=None,
                        help="Optional path to write the complete JSON result")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print the JSON result")
    parser.add_argument("--summary", action="store_true",
                        help="Print a human-readable summary instead of raw JSON (ignored with --output)")
    parser.add_argument("--check-schema", action="store_true",
                        help="Validate the result against contracts/engine-result.schema.json")
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parents[2]
    samples_dir = args.samples_dir or repo_root / "data" / "samples"
    schema_path = repo_root / "contracts" / "engine-result.schema.json"
    try:
        business, data = _load_scenario(samples_dir, args.scenario)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Could not load demo scenario: {exc}", file=sys.stderr)
        return 2

    result = run_analysis(business, data)
    if args.check_schema:
        errors = _validate_schema(result, schema_path)
        if errors:
            print("Schema validation failed:", file=sys.stderr)
            for error in errors:
                print(f"  - {error}", file=sys.stderr)
            return 3

    rendered = json.dumps(result, indent=2 if args.pretty else None, ensure_ascii=False, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
        print(f"Wrote analysis JSON to {args.output}")
        print(f"Scenario: {args.scenario} | status: {result.get('status')} | evidence: {result.get('evidence_level')}")
    elif args.summary:
        print(_render_summary(result, business))
    else:
        print(rendered)
    if result.get("status") == "failed":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
