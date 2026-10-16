import numpy as np
import pandas as pd
import pytest

from conftest import SAMPLES
from analytics_engine.validation import validate_all, validate_table


def codes(issues):
    return {i.code for i in issues}


def fin(rows, cols=("period", "revenue", "expenses")):
    return pd.DataFrame(rows, columns=list(cols))


# ---------- structure / input handling ------------------------------------
def test_unknown_dataset_name_raises():
    with pytest.raises(ValueError):
        validate_table(pd.DataFrame(), "nonsense")


def test_none_and_empty_input_are_errors_not_crashes():
    assert "no_data" in codes(validate_table(None, "financials").errors)
    assert "empty_dataset" in codes(validate_table(pd.DataFrame(), "financials").errors)


def test_missing_required_column_is_error():
    r = validate_table(pd.DataFrame({"period": ["2025-01"]}), "financials")
    assert "missing_required_columns" in codes(r.errors)
    assert not r.is_valid and not r.is_usable and r.clean is None


def test_column_names_are_normalised():
    r = validate_table(pd.DataFrame({" Period ": ["2025-01"], "REVENUE": [100]}), "financials")
    assert r.is_usable and list(r.clean["period"]) == ["2025-01"]


def test_absent_optional_columns_warn_and_stay_missing_not_zero():
    r = validate_table(fin([("2025-01", 100, 80)], ("period", "revenue", "expenses")), "financials")
    assert "missing_optional_column" in codes(r.warnings)  # expenses_complete absent
    assert r.clean["expenses_complete"].isna().all()
    r2 = validate_table(pd.DataFrame({"period": ["2025-01"], "revenue": [100]}), "financials")
    assert r2.clean["expenses"].isna().all()  # NaN, never 0


# ---------- periods --------------------------------------------------------
@pytest.mark.parametrize("bad", ["2025-13", "Oct 2025", "2025/01", "2025-1", "", None, "2025-01-15"])
def test_invalid_periods_are_errors_and_rows_dropped(bad):
    r = validate_table(fin([("2025-01", 100, 80), (bad, 90, 70)]), "financials")
    assert "invalid_period" in codes(r.errors)
    assert list(r.clean["period"]) == ["2025-01"]
    assert r.is_usable and not r.is_valid


# ---------- numeric handling ----------------------------------------------
def test_formatted_strings_become_missing_with_warning_never_zero():
    r = validate_table(fin([("2025-01", 100, 80), ("2025-02", "₹25,000", 70)]), "financials")
    assert "invalid_numeric" in codes(r.warnings)
    row = r.clean[r.clean.period == "2025-02"].iloc[0]
    assert np.isnan(row["revenue"])


def test_missing_values_are_not_filled_with_zero():
    r = validate_table(fin([("2025-01", 100, 80), ("2025-02", None, 70)]), "financials")
    assert "missing_values" in codes(r.warnings)
    assert r.clean["revenue"].isna().sum() == 1
    assert (r.clean["revenue"].fillna(-1) != 0).all()


def test_infinite_values_treated_as_invalid():
    r = validate_table(fin([("2025-01", 100, 80), ("2025-02", np.inf, 70)]), "financials")
    assert "invalid_numeric" in codes(r.warnings)


def test_negative_values_flagged_not_removed():
    r = validate_table(fin([("2025-01", 100, 80), ("2025-02", -50, 70)]), "financials")
    assert "negative_value" in codes(r.warnings)
    assert len(r.clean) == 2
    assert r.clean.loc[r.clean.period == "2025-02", "needs_review"].item() is True or \
        bool(r.clean.loc[r.clean.period == "2025-02", "needs_review"].item())


def test_all_revenue_unusable_is_error():
    r = validate_table(fin([("2025-01", "abc", 80), ("2025-02", None, 70)]), "financials")
    assert "no_usable_values" in codes(r.errors)


# ---------- duplicates -----------------------------------------------------
def test_exact_duplicates_removed_with_warning():
    r = validate_table(fin([("2025-01", 100, 80), ("2025-01", 100, 80), ("2025-02", 90, 70)]),
                       "financials")
    assert "duplicate_rows" in codes(r.warnings)
    assert len(r.clean) == 2 and r.is_valid


def test_conflicting_duplicates_are_error_and_all_excluded():
    r = validate_table(fin([("2025-01", 100, 80), ("2025-01", 120, 80), ("2025-02", 90, 70)]),
                       "financials")
    assert "conflicting_duplicates" in codes(r.errors)
    assert list(r.clean["period"]) == ["2025-02"]


# ---------- outliers & gaps -----------------------------------------------
def test_outlier_flagged_but_kept():
    rows = [(f"2025-{m:02d}", 100, 80) for m in range(1, 8)] + [("2025-08", 5000, 80)]
    r = validate_table(fin(rows), "financials")
    assert "suspicious_outlier" in codes(r.warnings)
    assert len(r.clean) == 8
    assert bool(r.clean.loc[r.clean.period == "2025-08", "needs_review"].item())


def test_no_outlier_judgement_with_too_few_observations():
    r = validate_table(fin([("2025-01", 100, 80), ("2025-02", 5000, 80)]), "financials")
    assert "suspicious_outlier" not in codes(r.warnings)


def test_missing_months_reported():
    r = validate_table(fin([("2025-01", 100, 80), ("2025-04", 90, 70)]), "financials")
    msg = " ".join(i.message for i in r.warnings if i.code == "missing_months")
    assert "2025-02" in msg and "2025-03" in msg


# ---------- expenses_complete flag ----------------------------------------
def test_expenses_complete_parsing():
    df = pd.DataFrame({"period": ["2025-01", "2025-02", "2025-03", "2025-04"],
                       "revenue": [1, 2, 3, 4], "expenses": [1, 1, 1, 1],
                       "expenses_complete": ["True", "no", "", "maybe"]})
    r = validate_table(df, "financials")
    assert list(r.clean["expenses_complete"]) == [True, False, None, None]
    assert "invalid_flag" in codes(r.warnings)


# ---------- customers & products ------------------------------------------
def test_customer_rows_without_id_are_excluded():
    df = pd.DataFrame({"period": ["2025-01", "2025-01"], "customer_id": ["C1", None],
                       "amount_spent": [100, 50]})
    r = validate_table(df, "customers")
    assert "missing_identifier" in codes(r.warnings)
    assert list(r.clean["customer_id"]) == ["C1"]


def test_customer_duplicate_key_conflict():
    df = pd.DataFrame({"period": ["2025-01", "2025-01"], "customer_id": ["C1", "C1"],
                       "amount_spent": [100, 150]})
    assert "conflicting_duplicates" in codes(validate_table(df, "customers").errors)


def test_product_required_columns():
    r = validate_table(pd.DataFrame({"period": ["2025-01"], "product_id": ["P1"]}), "products")
    assert "missing_required_columns" in codes(r.errors)


def test_validate_all_skips_absent_tables():
    out = validate_all({"financials": fin([("2025-01", 100, 80)]), "products": None})
    assert set(out) == {"financials"}


# ---------- result structure ----------------------------------------------
def test_report_is_json_serialisable():
    import json
    r = validate_table(fin([("2025-13", 1, 1), ("2025-01", 100, 80)]), "financials")
    json.dumps(r.to_dict())  # must not raise


# ---------- sample datasets ------------------------------------------------
@pytest.mark.parametrize("scenario,tables", [
    ("retail", ["financials", "customers", "products"]),
    ("service", ["financials", "customers"]),
    ("cold_start", ["financials"]),
])
def test_clean_sample_datasets_have_no_errors(scenario, tables):
    for t in tables:
        df = pd.read_csv(SAMPLES / scenario / f"{t}.csv")
        r = validate_table(df, t)
        assert r.is_valid, (scenario, t, [i.message for i in r.errors])
        assert r.rows_out == r.rows_in


def test_messy_sample_triggers_every_expected_rule():
    r = validate_table(pd.read_csv(SAMPLES / "messy" / "financials.csv"), "financials")
    assert {"invalid_period", "conflicting_duplicates"} <= codes(r.errors)
    assert {"duplicate_rows", "invalid_numeric", "missing_values", "negative_value",
            "suspicious_outlier", "invalid_flag"} <= codes(r.warnings)
    assert r.is_usable and not r.is_valid
