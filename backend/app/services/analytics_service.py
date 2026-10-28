"""Adapter between the BizIQ API and the analytics engine."""

from typing import Any, Callable, Dict

import pandas as pd

from app.schemas.business import BusinessRead
from analytics_engine.api_adapter import run_for_service

AnalyticsEngine = Callable[[BusinessRead], Dict[str, Any]]


def real_engine(business: BusinessRead) -> Dict[str, Any]:
    """Run analysis using available data without fabricating financial records."""
    data = {
        "financials": None,
        "customers": None,
        "products": None,
    }

    # The current API has no connected financial/customer/product repository.
    # Keep unavailable datasets as None rather than inventing data.
    return run_for_service(business, data)


def get_analytics_engine() -> AnalyticsEngine:
    """Return the real analytics engine adapter."""
    return real_engine


def mock_engine(business: BusinessRead) -> Dict[str, Any]:
    """Deterministic mock engine for tests only."""
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
                "title": "Sample finding",
                "description": "Mock finding for tests.",
                "metric_name": "expense_ratio",
                "metric_value": 76.71,
                "severity": "warning",
                "evidence": ["Mock test data"],
            }
        ],
        "recommendations": [
            {
                "recommendation_id": "r-001",
                "title": "Sample recommendation",
                "issue": "Mock issue",
                "reason": "Mock reason",
                "action": "Mock action",
                "priority": "high",
                "supporting_finding_ids": ["f-001"],
                "evidence": ["Mock test data"],
                "kpi": "Expense ratio",
                "expected_direction": "decrease",
            }
        ],
        "evidence_level": "medium",
        "benchmark_status": "unavailable",
        "method_version": "mock-test-0.1.0",
        "limitations": ["Mock output for tests only."],
    }
