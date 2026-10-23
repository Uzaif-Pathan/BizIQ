import json

import numpy as np
import pandas as pd
import pytest

from conftest import SAMPLES
from analytics_engine.ml import segment_customers
from analytics_engine.ml import segmentation as seg
from analytics_engine.validation import validate_table

MONTHS = [f"2025-{m:02d}" for m in range(1, 13)]


def make_customers(groups, months=MONTHS, seed=0):
    """groups: list of (n_customers, active_months(list), spend_per_month). Returns raw df."""
    rng = np.random.default_rng(seed)
    rows, cid = [], 0
    for n, act, spend in groups:
        for _ in range(n):
            cid += 1
            for p in act:
                rows.append((p, f"C{cid:03d}", float(spend * rng.uniform(0.9, 1.1)), 3))
    return pd.DataFrame(rows, columns=["period", "customer_id", "amount_spent", "transactions"])


def clean(df):
    return validate_table(df, "customers").clean


THREE = [(15, MONTHS, 9000), (15, MONTHS[:2], 300), (15, MONTHS[:6], 1200)]


def test_clear_groups_are_found_and_evaluated():
    m = segment_customers(clean(make_customers(THREE)))
    d = m["details"]
    assert m["status"] == "ok"
    assert d["k"] == 3 and d["silhouette"] > 0.5 and d["stability_ari"] == 1.0
    assert sum(s["customers"] for s in d["segments"]) == 45
    assert sum(s["spend_share_pct"] for s in d["segments"]) == pytest.approx(100, abs=0.5)
    assert set(d["k_scores"]) <= {"2", "3", "4", "5"}
    assert d["features"] == list(seg.FEATURES) and "StandardScaler" in d["scaling"]


def test_segment_labels_follow_the_rules():
    d = segment_customers(clean(make_customers(THREE)))["details"]
    names = {s["name"] for s in d["segments"]}
    assert "Loyal high-value" in names
    assert "Lapsed / inactive" in names  # the 2-months-then-gone group
    top = d["segments"][0]  # sorted by spend share
    assert top["name"] == "Loyal high-value" and top["customers"] == 15


def test_none_and_empty_are_not_applicable():
    assert segment_customers(None)["status"] == "not_applicable"
    assert segment_customers(pd.DataFrame())["status"] == "not_applicable"


def test_too_few_customers_is_skipped_with_reason():
    m = segment_customers(clean(make_customers([(8, MONTHS, 1000)])))
    assert m["status"] == "skipped_insufficient_data"
    assert m["details"]["skip_code"] == "too_few_customers" and "20" in m["details"]["reason"]


def test_too_few_months_is_skipped():
    m = segment_customers(clean(make_customers([(30, MONTHS[:2], 1000)])))
    assert m["details"]["skip_code"] == "too_few_months"


def test_identical_customers_are_skipped_not_clustered():
    m = segment_customers(clean(pd.DataFrame(
        [(p, f"C{i}", 1000.0, 1) for i in range(30) for p in MONTHS],
        columns=["period", "customer_id", "amount_spent", "transactions"])))
    assert m["status"] == "skipped_insufficient_data"
    assert m["details"]["skip_code"] == "no_variation"


def test_single_blob_without_structure_is_not_split_into_fake_segments():
    rng = np.random.default_rng(1)
    rows = [(p, f"C{i:03d}", float(rng.normal(5000, 700)), 2)
            for i in range(60) for p in MONTHS]  # everyone active every month, similar spend
    m = segment_customers(clean(pd.DataFrame(rows, columns=["period", "customer_id", "amount_spent", "transactions"])))
    assert m["status"] == "skipped_insufficient_data"
    assert "segments" not in m["details"]


def test_result_is_deterministic():
    c = clean(make_customers(THREE))
    assert segment_customers(c) == segment_customers(c)


def test_input_not_modified_and_json_strict():
    c = clean(make_customers(THREE))
    before = c.copy()
    m = segment_customers(c)
    pd.testing.assert_frame_equal(c, before)
    json.dumps(m, allow_nan=False)


def test_missing_spend_values_are_ignored_not_zero():
    df = make_customers(THREE)
    df.loc[df.index[:10], "amount_spent"] = None
    m = segment_customers(clean(df))
    assert m["status"] in ("ok", "skipped_insufficient_data")  # no crash, no zero-fill


def test_never_raises_on_garbage():
    bad = pd.DataFrame({"period": ["x"], "customer_id": [1], "amount_spent": ["y"]})
    assert segment_customers(bad)["status"] in ("failed", "skipped_insufficient_data", "not_applicable")


def test_only_the_latest_12_months_are_used():
    old = make_customers([(30, [f"2023-{m:02d}" for m in range(1, 13)], 5000)], seed=3)
    new = make_customers(THREE, seed=4)
    d = segment_customers(clean(pd.concat([old, new], ignore_index=True)))["details"]
    assert d["window"] == "2025-01/2025-12" and d["n_customers"] == 45


@pytest.mark.parametrize("scenario,expected", [("retail", "ok"), ("service", "ok")])
def test_sample_datasets(scenario, expected):
    c = clean(pd.read_csv(SAMPLES / scenario / "customers.csv"))
    m = segment_customers(c)
    assert m["status"] == expected and m["details"]["silhouette"] >= seg.MIN_SILHOUETTE


def test_model_object_matches_contract_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((SAMPLES.parents[1] / "contracts" / "analysis-result.schema.json").read_text())
    ref = {"$ref": "#/$defs/model", "$defs": schema["$defs"]}
    for m in (segment_customers(clean(make_customers(THREE))), segment_customers(None)):
        jsonschema.validate(m, ref)
