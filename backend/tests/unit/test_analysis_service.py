"""Analysis service behaviour that needs no web server or database."""
import pandas as pd

from analytics_engine.api_adapter import EngineRunFailed, run_for_service
from app.repositories.memory import InMemoryAnalysisRepository, InMemoryBusinessRepository
from app.schemas.analysis import AnalysisStatus
from app.schemas.business import BusinessCreate
from app.services import analysis_service
from app.services.analytics_service import real_engine

from pathlib import Path

SAMPLES = Path(__file__).resolve().parents[3] / "data" / "samples" / "retail"


def _setup():
    brepo, arepo = InMemoryBusinessRepository(), InMemoryAnalysisRepository()
    business = brepo.create(BusinessCreate(name="Demo Store", industry="grocery", business_type="retail"))
    return business, brepo, arepo


def test_engine_failure_keeps_the_engine_reason():
    business, brepo, arepo = _setup()

    def engine(_b):
        raise EngineRunFailed("no_usable_data", "None of the provided tables could be used.")

    result = analysis_service.run_analysis(business, engine, arepo, brepo)
    assert result.status == AnalysisStatus.FAILED
    assert result.error_message == "None of the provided tables could be used."
    assert result.error_code == "no_usable_data"


def test_unexpected_error_hides_internal_details():
    business, brepo, arepo = _setup()

    def engine(_b):
        raise RuntimeError("secret internal detail")

    result = analysis_service.run_analysis(business, engine, arepo, brepo)
    assert result.status == AnalysisStatus.FAILED
    assert "secret" not in result.error_message
    assert result.error_code is None


def test_current_real_engine_without_data_fails_with_a_reason():
    business, brepo, arepo = _setup()
    result = analysis_service.run_analysis(business, real_engine, arepo, brepo)
    assert result.status == AnalysisStatus.FAILED and result.error_code == "no_usable_data"


def test_engine_extras_survive_the_api_model_and_the_repository():
    business, brepo, arepo = _setup()
    data = {t: pd.read_csv(SAMPLES / f"{t}.csv") for t in ("financials", "customers", "products")}
    result = analysis_service.run_analysis(business, lambda b: run_for_service(b, data), arepo, brepo)
    assert result.status == AnalysisStatus.COMPLETED
    saved = arepo.get(result.analysis_id)
    assert set(saved.series) == {"financial_monthly", "customer_monthly", "products"}
    assert saved.health_score and saved.engine_status == "completed"
    assert saved.recommendations and saved.recommendations[0].rule_id
    assert saved.metrics.revenue == 3726825.0
