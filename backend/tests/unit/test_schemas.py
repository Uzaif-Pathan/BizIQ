import json
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas import (
    AnalysisResult,
    BusinessCreate,
    BusinessRead,
    BusinessUpdate,
    Metrics,
    ValidationIssueCreate,
)

REPO_ROOT = Path(__file__).resolve().parents[3]
CONTRACTS = REPO_ROOT / "contracts"
EXAMPLES = sorted((CONTRACTS / "examples").glob("*.json"))


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_example_files_exist():
    assert len(EXAMPLES) >= 2


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_examples_match_pydantic_contract(path):
    result = AnalysisResult.model_validate(_load(path))
    assert result.business_id


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_examples_match_json_schema(path):
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(CONTRACTS / "analysis-result.schema.json")
    jsonschema.Draft202012Validator.check_schema(schema)
    jsonschema.Draft202012Validator(schema).validate(_load(path))


def test_json_schema_rejects_failed_run_without_message():
    jsonschema = pytest.importorskip("jsonschema")
    schema = _load(CONTRACTS / "analysis-result.schema.json")
    bad = _load(CONTRACTS / "examples" / "analysis-result.failed.example.json")
    bad["error_message"] = None
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema).validate(bad)


def test_failed_result_requires_error_message():
    data = _load(CONTRACTS / "examples" / "analysis-result.failed.example.json")
    data["error_message"] = None
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(data)


def test_recommendation_needs_supporting_findings():
    data = _load(CONTRACTS / "examples" / "analysis-result.completed.example.json")
    data["recommendations"][0]["supporting_finding_ids"] = []
    with pytest.raises(ValidationError):
        AnalysisResult.model_validate(data)


def test_missing_metrics_stay_null_not_zero():
    metrics = Metrics()
    assert metrics.revenue is None
    assert metrics.profit_margin is None


def test_metrics_allow_extra_numeric_values():
    metrics = Metrics(revenue=100, revenue_growth_mom=5.2)
    assert metrics.model_dump()["revenue_growth_mom"] == 5.2


def test_business_create_defaults_and_trimming():
    b = BusinessCreate(name="  Sharma Traders  ", industry="Grocery", business_type="retail")
    assert b.name == "Sharma Traders"
    assert b.country == "India"
    assert b.stage.value == "established"
    assert b.goals == []


def test_business_create_rejects_bad_type():
    with pytest.raises(ValidationError):
        BusinessCreate(name="Shop", industry="Grocery", business_type="spaceship")


def test_business_update_must_have_a_field():
    with pytest.raises(ValidationError):
        BusinessUpdate()


def test_business_update_rejects_null_required_field():
    with pytest.raises(ValidationError):
        BusinessUpdate(name=None)


def test_business_update_rejects_unknown_field():
    with pytest.raises(ValidationError):
        BusinessUpdate(nmae="typo")


def test_business_update_partial_ok():
    u = BusinessUpdate(city="Aurangabad")
    assert u.model_dump(exclude_unset=True) == {"city": "Aurangabad"}


def test_business_read_from_attributes():
    now = datetime.now(timezone.utc)
    row = SimpleNamespace(
        id=uuid4(),
        name="Sharma Traders",
        industry="Grocery",
        business_type="retail",
        stage="established",
        city=None,
        district=None,
        state="Maharashtra",
        country="India",
        employee_count=4,
        description=None,
        goals=["Reduce expenses"],
        latest_analysis_status=None,
        created_at=now,
        updated_at=now,
    )
    read = BusinessRead.model_validate(row)
    assert read.state == "Maharashtra"
    assert read.latest_analysis_status is None


def test_validation_issue_row_number_is_one_based():
    with pytest.raises(ValidationError):
        ValidationIssueCreate(severity="error", code="invalid_number", message="bad", row_number=0)
