"""Benchmark loading and lookup, using the real ASUSE file (no database needed)."""
from pathlib import Path

import pytest

from app.services.benchmark_loader import rows_from_csv
from app.services.benchmark_service import match_industry, match_state, select_benchmarks

CSV = Path(__file__).resolve().parents[3] / "database" / "reference_data" / "biziq_asuse_2025_benchmark.csv"


@pytest.fixture(scope="module")
def rows():
    rows, _ = rows_from_csv(CSV)
    return [r | {"source_name": "ASUSE 2025 (Jan-Dec 2025)"} for r in rows]


def test_loader_skips_zero_reported_rows_and_keeps_counts_honest():
    rows, counts = rows_from_csv(CSV)
    assert counts["rows_in_file"] == 7128 and counts["skipped_zero_reported"] == 330
    assert counts["rows_loaded"] == 7128 - 330 - counts["skipped_unusable"] == len(rows)
    assert all(r["metric_value"] > 0 for r in rows)  # no fake zero benchmarks
    assert {r["geography_level"] for r in rows} == {"NATIONAL", "STATE"}
    assert all(r["state"] is None for r in rows if r["geography_level"] == "NATIONAL")


def test_loader_rejects_a_file_with_missing_columns(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("geography,value\nIndia,5\n")
    with pytest.raises(ValueError):
        rows_from_csv(bad)


def test_industry_matching():
    assert match_industry("Grocery retail", "retail")["activity"] == "Other Retail Trade"
    assert match_industry("restaurant", "other")["broad_sector"] == "Other Services"
    assert match_industry("tailoring studio", "service")["match"] == "business_type"
    assert match_industry("space tourism", "other") == {"broad_sector": "All", "activity": "All", "match": "none"}


def test_state_matching_handles_symbols_and_aliases():
    states = ["Maharashtra", "Jammu & Kashmir", "Puduchery"]
    assert match_state("maharashtra ", states) == "Maharashtra"
    assert match_state("Jammu and Kashmir", states) == "Jammu & Kashmir"
    assert match_state("Puducherry", states) == "Puduchery"
    assert match_state("Atlantis", states) is None and match_state(None, states) is None


def test_retail_in_maharashtra_gets_state_and_national_rows_with_labels(rows):
    out = select_benchmarks(rows, {"industry": "grocery retail", "business_type": "retail", "state": "Maharashtra"})
    assert out["status"] == "available" and out["matched_state"] == "Maharashtra"
    levels = {(i["geography_level_used"], i["industry_used"]) for i in out["items"]}
    assert ("state", "Trade") in levels and ("national", "Other Retail Trade") in levels
    for i in out["items"]:
        assert i["year"] == 2025 and i["source"] and i["definition"] and i["value"] > 0
        assert i["metric"] != "hired_workers_count"
    assert any("not compare" in n or "do not compare" in n for n in out["notes"])


def test_unknown_state_falls_back_to_national_and_says_so(rows):
    out = select_benchmarks(rows, {"industry": "retail", "business_type": "retail", "state": "Atlantis"})
    assert {i["geography_level_used"] for i in out["items"]} == {"national"}
    assert any("Atlantis" in n for n in out["notes"])


def test_unmatched_industry_is_partial_not_invented(rows):
    out = select_benchmarks(rows, {"industry": "space tourism", "business_type": "other", "state": None})
    assert out["status"] == "partial" and out["matched_industry"]["match"] == "none"


def test_no_rows_means_unavailable(rows):
    out = select_benchmarks([], {"industry": "retail", "business_type": "retail", "state": "Maharashtra"})
    assert out["status"] == "unavailable" and out["items"] == []


# ---------------- scope labels (item 4) ----------------------------------------------------
def test_state_rows_are_labelled_broad_and_national_rows_detailed(rows):
    out = select_benchmarks(rows, {"industry": "grocery retail", "business_type": "retail", "state": "Maharashtra"})
    by_level = {i["geography_level_used"]: i for i in out["items"]}
    assert by_level["state"]["specificity"] == "broad_sector" and by_level["state"]["industry_used"] == "Trade"
    assert by_level["national"]["specificity"] == "detailed_activity"
    assert by_level["national"]["industry_used"] == "Other Retail Trade"
    assert all(i["specificity_note"] for i in out["items"])
    assert any("not equally specific" in n for n in out["notes"])


def test_all_industry_rows_are_labelled_all_industries(rows):
    out = select_benchmarks(rows, {"industry": "space tourism", "business_type": "other", "state": None})
    assert out["items"] and {i["specificity"] for i in out["items"]} == {"all_industries"}
    assert not any("not equally specific" in n for n in out["notes"])  # only one kind of row, nothing to contrast


def test_national_only_result_has_no_mixed_specificity_note(rows):
    out = select_benchmarks(rows, {"industry": "retail", "business_type": "retail", "state": None})
    assert {i["specificity"] for i in out["items"]} == {"detailed_activity"}
    assert not any("not equally specific" in n for n in out["notes"])


# ---------------- ASUSE figures must never reach the health score (item 2) ------------------
def test_asuse_items_do_not_change_the_health_score(rows):
    from analytics_engine.scoring import compute_health_score

    fin = {"metrics": {k: {"value": v} for k, v in
                       dict(profit_margin_pct=20.0, revenue_12m_growth_pct=10.0, expenses_yoy_pct=5.0,
                            revenue_yoy_pct=10.0).items()}, "monthly": [], "trend": {}}
    asuse = select_benchmarks(rows, {"industry": "grocery retail", "business_type": "retail",
                                     "state": "Maharashtra"})["items"]
    assert asuse and not {i["metric"] for i in asuse} & {"profit_margin_pct", "gross_margin_pct"}
    with_asuse = compute_health_score(fin, None, None, asuse)
    without = compute_health_score(fin, None, None, None)
    assert with_asuse["score"] == without["score"]
    assert all(c["basis"] != "benchmark" for c in with_asuse["components"])
