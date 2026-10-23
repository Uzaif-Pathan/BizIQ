"""Analytics engine adapter.

The API never calls analytics code directly. It calls an "engine": a function that
takes a business and returns a dict in the agreed contract shape (metrics, findings,
recommendations, evidence_level, benchmark_status, ...). The service adds the ids,
status and timestamps.

Today the engine is `mock_engine`. When Person 2's real engine is ready, write a
small function here that calls it and returns the same dict, then return it from
`get_analytics_engine()`. No route has to change.
"""

from typing import Any, Callable, Dict

from app.schemas.business import BusinessRead

AnalyticsEngine = Callable[[BusinessRead], Dict[str, Any]]


def mock_engine(business: BusinessRead) -> Dict[str, Any]:
    """Fixed, predictable sample output. Not real analysis."""
    return {
        "metrics": {
            "revenue": 286800,
            "expenses": 220000,
            "profit": 66800,
            "profit_margin": 23.29,
        },
        "findings": [
            {
                "finding_id": "f-001",
                "category": "financial",
                "title": "Expenses take most of revenue",
                "description": "Recorded expenses are 76.71% of recorded revenue (sample data).",
                "metric_name": "expense_ratio",
                "metric_value": 76.71,
                "severity": "warning",
                "evidence": ["revenue = 286800 INR", "expenses = 220000 INR"],
            }
        ],
        "recommendations": [
            {
                "recommendation_id": "r-001",
                "title": "Review the largest expense categories",
                "issue": "Expenses are 76.71% of revenue.",
                "reason": "Triggered by finding f-001: the expense ratio is high.",
                "action": "List expenses by category and check the three largest for savings.",
                "priority": "high",
                "supporting_finding_ids": ["f-001"],
                "evidence": ["expense_ratio = 76.71%"],
                "kpi": "Expense ratio (% of revenue)",
                "expected_direction": "decrease",
            }
        ],
        "evidence_level": "medium",
        "benchmark_status": "unavailable",
        "method_version": "mock-0.1.0",
        "limitations": [
            "This is mock output for development. It is not calculated from real data.",
            "Benchmark comparison is unavailable.",
        ],
    }


def get_analytics_engine() -> AnalyticsEngine:
    """FastAPI dependency. Swap the return value to use the real engine."""
    return mock_engine
