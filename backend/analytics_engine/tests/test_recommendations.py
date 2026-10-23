import json
import re
from pathlib import Path

import pytest

from conftest import SAMPLES
from analytics_engine.recommendations import RULES, build_recommendations
from analytics_engine.recommendations import engine as eng


def F(id_, type_, severity="medium", metric="m", evidence="Evidence text."):
    return {"id": id_, "type": type_, "metric": metric, "value": 1.0, "evidence": evidence, "severity": severity}


def one(findings, btype="retail", **kw):
    recs = build_recommendations(findings, btype, **kw)
    assert len(recs) == 1, recs
    return recs[0]


# ---------------- firing rules ---------------------------------------------------------------
@pytest.mark.parametrize("rule", RULES, ids=lambda r: r.id)
def test_every_rule_fires_on_each_of_its_finding_types(rule):
    for t in rule.types:
        rec = one([F("X-1", t, "medium", metric="the_metric")])
        assert rec["id"] == f"REC-{rule.id}" and rec["rule_id"] == rule.id
        assert rec["finding_ids"] == ["X-1"] and rec["supporting_metric"] == "the_metric"
        assert rec["issue"] and rec["action"] and rec["kpi"] and rec["rationale"] and rec["evidence"]


def test_info_findings_and_unknown_types_produce_nothing():
    assert build_recommendations([F("A", "profit_margin_level", "info"), F("B", "no_such_type", "high")]) == []
    assert build_recommendations([]) == [] and build_recommendations(None) == []


def test_malformed_findings_are_ignored_not_fatal():
    bad = [None, "x", {}, {"id": "A", "type": "loss_months"}, F("B", "loss_months", "weird")]
    assert build_recommendations(bad) == []


def test_related_findings_are_grouped_into_one_recommendation():
    rec = one([F("FIN-MARGIN", "profit_margin_level", "high"), F("FIN-LOSSMONTHS", "loss_months", "medium")])
    assert rec["id"] == "REC-LOSS" and rec["finding_ids"] == ["FIN-MARGIN", "FIN-LOSSMONTHS"]
    assert "Evidence text. Evidence text." == rec["evidence"]


def test_many_findings_of_one_kind_are_summarised():
    fs = [F(f"PRD-DECLINE-P{i}", "product_revenue_declining", "low") for i in range(5)]
    rec = one(fs)
    assert len(rec["finding_ids"]) == 5 and "+2 more" in rec["evidence"]


# ---------------- priority & order -------------------------------------------------------------
@pytest.mark.parametrize("sev,prio", [("low", "low"), ("medium", "medium"), ("high", "high")])
def test_priority_comes_from_highest_severity(sev, prio):
    assert one([F("A", "loss_months", sev)])["priority"] == prio


def test_priority_uses_the_strongest_finding_in_a_group_and_leads_the_ids():
    rec = one([F("LOW", "profit_margin_level", "low"), F("HIGH", "loss_months", "high")])
    assert rec["priority"] == "high" and rec["finding_ids"][0] == "HIGH"
    assert rec["supporting_metric"] == "m"


def test_recommendations_sorted_high_to_low_then_rule_order():
    recs = build_recommendations([F("1", "revenue_volatility", "low"), F("2", "loss_months", "high"),
                                  F("3", "customer_concentration", "medium"),
                                  F("4", "expense_definition_incomplete", "medium")], "retail")
    assert [r["priority"] for r in recs] == ["high", "medium", "medium", "low"]
    assert [r["rule_id"] for r in recs][1:3] == ["EXPENSE-LIST", "CUSTOMER-CONCENTRATION"]  # rule order
    assert len({r["id"] for r in recs}) == len(recs)


# ---------------- business type ---------------------------------------------------------------
def test_wording_differs_by_business_type_and_unknown_falls_back_to_generic():
    f = [F("A", "customer_retention_low", "medium")]
    retail, service, other = (one(f, t)["action"] for t in ("retail", "service", "other"))
    assert len({retail, service, other}) == 3
    assert one(f, "Retail ")["action"] == retail          # normalised
    for odd in (None, "", "restaurant", 42):
        assert one(f, odd)["action"] == other


def test_every_rule_has_all_three_action_variants():
    for r in RULES:
        assert set(r.actions) == {"retail", "service", "other"} and len(set(r.actions.values())) == 3, r.id


# ---------------- evidence level / direction / honesty -------------------------------------------
def test_low_evidence_adds_caveat_only_then():
    f = [F("A", "loss_months", "high")]
    assert "caveat" in one(f, evidence_level="low") and "caveat" not in one(f, evidence_level="high")
    assert "caveat" not in one(f)


def test_data_quality_rules_have_no_expected_direction_but_business_rules_do():
    dq = {"EXPENSE-LIST", "DATA-REVIEW", "DATA-COVERAGE"}
    for r in RULES:
        rec = one([F("A", r.types[0], "medium")])
        if r.id in dq:
            assert rec["expected_direction"] is None, r.id
        else:
            assert rec["expected_direction"]["direction"] in ("increase", "decrease"), r.id


def test_no_promises_in_any_recommendation_text():
    banned = re.compile(r"guarantee|will (increase|boost|grow|double|improve)|ensure (growth|profit|sales)|"
                        r"\bsure\b|definitely|certain(ly)? to", re.I)
    for r in RULES:
        for text in (r.issue, r.kpi, *r.actions.values()):
            assert not banned.search(text), (r.id, text)
        assert "not a guaranteed result" in one([F("A", r.types[0], "low")])["rationale"]


def test_rule_ids_unique_and_rationale_names_findings_and_rule():
    assert len({r.id for r in RULES}) == len(RULES)
    rec = one([F("FIN-X", "loss_months", "high")])
    assert "LOSS" in rec["rationale"] and "FIN-X" in rec["rationale"] and "retail" in rec["rationale"]


def test_input_findings_are_not_modified_and_output_is_strict_json():
    fs = [F("A", "loss_months", "high")]
    before = json.dumps(fs)
    recs = build_recommendations(fs)
    assert json.dumps(fs) == before
    json.dumps(recs, allow_nan=False)


# ---------------- drift guard: every rule listens to a finding type that really exists ----------------
def test_rule_types_exist_in_the_finding_builders():
    src = "".join(p.read_text() for p in Path(eng.__file__).parents[1].glob("*/findings.py"))
    for r in RULES:
        for t in r.types:
            prefix = t.rsplit("_", 1)[0] + "_{"          # e.g. f"revenue_trend_{d}"
            assert f'"{t}"' in src or prefix in src, f"{r.id}: no finding builder produces '{t}'"


# ---------------- real pipeline -----------------------------------------------------------------
def _findings(scenario):
    import pandas as pd
    import analytics_engine.customers as C, analytics_engine.financial as F_, analytics_engine.products as P
    from analytics_engine.validation import validate_table

    def load(t):
        p = SAMPLES / scenario / f"{t}.csv"
        return validate_table(pd.read_csv(p), t).clean if p.exists() else None
    return (F_.build_financial_findings(F_.analyze_financials(load("financials")))
            + C.build_customer_findings(C.analyze_customers(load("customers")))
            + P.build_product_findings(P.analyze_products(load("products"))))


@pytest.mark.parametrize("scenario,btype,expected", [
    ("retail", "retail", {"PRODUCT-DECLINE"}),
    ("service", "service", {"EXPENSE-LIST"}),
    ("cold_start", "other", {"EXPENSE-LIST"}),
    ("messy", "retail", {"EXPENSE-LIST", "DATA-REVIEW"}),
])
def test_sample_datasets(scenario, btype, expected):
    fs = _findings(scenario)
    recs = build_recommendations(fs, btype)
    assert {r["rule_id"] for r in recs} == expected
    ids = {f["id"] for f in fs}
    assert all(r["finding_ids"] and set(r["finding_ids"]) <= ids for r in recs)  # always traceable


def test_recommendations_match_contract_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SAMPLES.parents[1] / "contracts" / "analysis-result.schema.json").read_text())
    ref = {"$ref": "#/$defs/recommendation", "$defs": schema["$defs"]}
    recs = build_recommendations([F("A", t, "high") for r in RULES for t in r.types], "service", "low")
    assert len(recs) == len(RULES)
    for rec in recs:
        jsonschema.validate(rec, ref)
