"""Adapter between the BizIQ API and the analytics engine."""

from typing import Any, Callable, Dict, Optional

from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.dependencies import get_db_optional
from app.schemas.business import BusinessRead
from app.services.data_loader import load_engine_data
from analytics_engine.api_adapter import run_for_service

AnalyticsEngine = Callable[[BusinessRead], Dict[str, Any]]


def real_engine(business: BusinessRead) -> Dict[str, Any]:
    """Engine with no stored data (used when no database is configured).

    Every table is None, so the run fails with "no usable data" rather than inventing numbers."""
    return run_for_service(business, {"financials": None, "customers": None, "products": None})


def get_analytics_engine(db: Optional[Session] = Depends(get_db_optional)) -> AnalyticsEngine:
    """Return the real engine. With a database, it reads the business's stored rows; without one it
    gets no data (the run then fails with a clear reason instead of inventing numbers)."""
    if db is None:
        return real_engine

    def engine(business: BusinessRead) -> Dict[str, Any]:
        return run_for_service(business, load_engine_data(db, int(business.id)))

    return engine


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
