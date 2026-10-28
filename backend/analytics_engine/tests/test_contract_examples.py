"""Every file in contracts/examples must validate against the contract it claims to follow."""
import json

import pytest

from conftest import SAMPLES

CONTRACTS = SAMPLES.parents[1] / "contracts"
EXAMPLES = sorted((CONTRACTS / "examples").glob("*.json"))


def _schema_for(path):
    return CONTRACTS / ("engine-result.schema.json" if path.name.startswith("engine-result") else "analysis-result.schema.json")


def test_examples_exist():
    assert {p.name for p in EXAMPLES} >= {"analysis-result.completed.example.json", "analysis-result.failed.example.json",
                                         "analysis-result.engine-retail.example.json", "engine-result.retail.example.json"}


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_matches_its_schema(path):
    jsonschema = pytest.importorskip("jsonschema")
    validator = jsonschema.Draft202012Validator(json.loads(_schema_for(path).read_text()))
    assert [e.message for e in validator.iter_errors(json.loads(path.read_text()))] == []


@pytest.mark.parametrize("path", [p for p in EXAMPLES if not p.name.startswith("engine-result")], ids=lambda p: p.name)
def test_api_examples_also_load_into_the_backend_model(path):
    pytest.importorskip("pydantic")
    try:
        from app.schemas.analysis import AnalysisResult
    except ImportError:
        pytest.skip("backend app package not importable")
    AnalysisResult(**json.loads(path.read_text()))
