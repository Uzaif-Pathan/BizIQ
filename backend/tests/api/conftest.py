import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_analysis_repo, get_business_repo
from app.main import app
from app.repositories.memory import (
    InMemoryAnalysisRepository,
    InMemoryBusinessRepository,
)
from app.services.analytics_service import get_analytics_engine, mock_engine


@pytest.fixture()
def client():
    """Fresh empty storage for every test."""
    business_repo = InMemoryBusinessRepository()
    analysis_repo = InMemoryAnalysisRepository()
    app.dependency_overrides[get_business_repo] = lambda: business_repo
    app.dependency_overrides[get_analysis_repo] = lambda: analysis_repo
    app.dependency_overrides[get_analytics_engine] = lambda: mock_engine
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture()
def business(client):
    r = client.post(
        "/api/v1/businesses",
        json={"name": "Sharma Traders", "industry": "Grocery", "business_type": "retail"},
    )
    assert r.status_code == 201
    return r.json()
