"""Docs must not drift from the code: every rule and every finding type a rule listens to is documented."""
from pathlib import Path

from analytics_engine.recommendations.rules import RULES

DOC = (Path(__file__).resolve().parents[3] / "docs" / "RECOMMENDATION_RULES.md").read_text()


def test_every_rule_is_documented():
    missing = [r.id for r in RULES if f"| {r.id} |" not in DOC]
    assert missing == []


def test_every_trigger_type_is_documented():
    missing = [t for r in RULES for t in r.types if f"`{t}`" not in DOC]
    assert missing == []


def test_documented_aims_match_code():
    for r in RULES:
        row = next(l for l in DOC.splitlines() if l.startswith(f"| {r.id} |"))
        if r.direction:
            assert f"`{r.expected_metric}` {r.direction}" in row, r.id
        else:
            assert "none (data quality)" in row, r.id
