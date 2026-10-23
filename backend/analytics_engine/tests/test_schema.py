import json

import pytest

from conftest import SAMPLES

SCHEMA_PATH = SAMPLES.parents[1] / "contracts" / "analysis-result.schema.json"


def test_schema_is_valid_json_schema():
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.Draft202012Validator.check_schema(json.loads(SCHEMA_PATH.read_text()))


def test_metric_definition_accepts_trend_extras_and_rejects_missing_value():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA_PATH.read_text())
    ref = {"$ref": "#/$defs/metric", "$defs": schema["$defs"]}
    jsonschema.validate({"value": 1.5, "unit": "percent_per_month", "period": "2025-01/2025-06",
                         "formula": "x", "direction": "increasing", "r_squared": 0.9,
                         "months_used": 6, "note": None}, ref)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"unit": "INR"}, ref)
