# BizIQ analytics engine and backend integration notes (Person 3)

This document describes how the backend should load imported data, call Person 2's engine, and return the shared API contract. Route definitions are in [`api-routes.md`](api-routes.md); schema and migration details are in [`DATABASE_SCHEMA.md`](DATABASE_SCHEMA.md).

## Engine entry point

Call `analytics_engine.run_analysis(business, data, benchmarks=None)` from the backend adapter. The engine is independent of FastAPI and PostgreSQL.

```python
from analytics_engine import run_analysis

result = run_analysis(
    business={
        "business_id": business_id,
        "business_type": "retail",  # retail | service | other
        "industry": industry,
        "location": location,
    },
    data={
        "financials": financials_df,  # optional pandas DataFrame
        "customers": customers_df,    # optional pandas DataFrame
        "products": products_df,      # optional pandas DataFrame
    },
    benchmarks=benchmarks,            # optional list; only pass verified benchmarks
)
```

The engine does not open files, connect to a database, or make network calls. The adapter fetches authorized rows, converts each dataset to a DataFrame, and passes those frames to the function. Persist the returned JSON-safe result and status metadata.

## Dataset expectations

- **Financials:** one row per business/month; `period` (`YYYY-MM` or parseable date), `revenue`; `expenses` and `expenses_complete` when available.
- **Customers:** customer-period activity with `business_id`, `period`, `customer_id`, `transactions`, `amount_spent`.
- **Products:** product-period data with `business_id`, `period`, `product_id`, `product_name`, `units_sold`, `revenue`, `cost`.
- Each table is optional. A missing table should be represented as `None`, not a fabricated zero-valued DataFrame. Missing values remain null/NaN and reduce coverage where relevant.
- Keep money in INR and periods in a consistent calendar-month representation. Avoid direct customer identifiers; the database uses anonymous `customer_ref` values.
- Enforce business/user authorization before querying rows. Do not trust a `business_id` from an untrusted client without checking ownership.

## Native engine result and API result

`run_analysis` returns the engine's native result. The API and frontend use the API contract (`backend/app/schemas/analysis.py` and `contracts/analysis-result.schema.json`). `analytics_engine/api_adapter.py` converts one format into the other.

| Native engine format | API contract |
| --- | --- |
| Metric object with `value`, `unit`, `period`, `formula`, `reason` | Flat numeric metric (null remains null); `profit_margin_pct` is exposed as `profit_margin`; details are preserved in `metric_details`. |
| Finding `id`, `type`, `metric`, `value`, `evidence` | Finding `finding_id`, `category`, `title`, `description`, `metric_name`, `metric_value`, `evidence`. |
| Recommendation `id`, `finding_ids`, `rationale` | Recommendation `recommendation_id`, `supporting_finding_ids`, `reason`, plus action/priority and optional metric/rule/caveat fields. |
| Native status `completed`, `partial`, or `failed` | API status `completed` or `failed`; native status is preserved in `engine_status` and limitations as applicable. |
| Evidence level `low`, `medium`, `high` | Same value; failed/insufficient results use `insufficient` where appropriate. |

The API's eight core result fields are always present: `analysis_id`, `business_id`, `status`, `metrics`, `findings`, `recommendations`, `evidence_level`, and `benchmark_status`. Optional engine fields include `limitations`, `engine_status`, `error_code`, `metric_details`, `health_score`, `models`, `validation`, `data_coverage`, and `series`.

- A metric value of `null` means unavailable. Do not display it as zero; consult `metric_details[key].reason`.
- `health_score` is a transparent rule-based indicator, not a probability of success or credit rating.
- Segmentation and forecast outputs include status/evaluation and should omit predictions when quality gates fail.
- Recommendation IDs in the API result are the IDs used by the progress endpoints.
- Detailed formulas and evidence-quality rules are documented in [`ENGINE_FORMULAS.md`](ENGINE_FORMULAS.md) and `backend/analytics_engine/README.md`.

## Database-backed import pipeline

The CSV API routes are documented in [`api-routes.md`](api-routes.md). An upload uses multipart form fields:
- `data_type`: `financials`, `customers`, or `products`
- `file`: UTF-8 `.csv`, maximum 5 MiB

The import service validates the CSV using the analytics engine's table validator. It records row counts and validation issues, and only accepted rows are normalized into the monthly tables. The uploaded file itself is not saved.

| Import type | Normalized storage |
| --- | --- |
| `financials` | `monthly_financials` |
| `customers` | `customer_activity` |
| `products` | `products_services` and `monthly_product_metrics` |

Unknown values remain `NULL`; they must not be converted to zero. Rows rejected by validation are not stored. Negative values rejected or downgraded to unknown by validation must be reviewed in the returned issues/warnings. Re-uploading a key already present replaces the overlapping business/month row (for customer and product imports, the corresponding customer/product key is part of the row identity); unrelated months remain unchanged.

**Important difference between storage modes:**

- With `DATABASE_URL` configured, the SQL repositories persist import metadata, validation issues, accepted normalized rows, analyses, and progress in PostgreSQL. Run Alembic migrations through `head` first.
- Without `DATABASE_URL`, in-memory repositories allow a quick API demo and basic tests. They keep import metadata/issues only, **not the accepted normalized rows**. Consequently, an upload in in-memory mode is not available as analysis input. All in-memory state is lost when the API process restarts, and benchmark lookup returns unavailable.

The import API currently accepts CSV only; the frontend `pages/data-input` does not yet contain an upload UI. The API contract is available for the frontend to call.

## Wiring the engine into the analysis service

Person 3 owns `backend/app/services/analytics_service.py`. The service should load data for the selected business and call `run_for_service` so the native engine result is mapped to the API result contract.

```python
from analytics_engine.api_adapter import run_for_service
from app.services.data_loader import load_engine_data

def real_engine(business):
    # `db` must be the active SQLAlchemy session for this request.
    data = load_engine_data(db, int(business.id))
    return run_for_service(business, data)
```

The exact dependency/session wiring depends on the current service signature. Avoid creating a second, unmanaged database session inside the adapter if a request-scoped session is already available. Do not put `analysis_id`, `business_id`, `status`, or timestamps into the engine output if `analysis_service.run_analysis` adds those fields separately.

If the engine cannot analyze the available data, surface its sanitized failure code/message rather than returning a success-shaped result with fabricated zero metrics. Do not return stack traces or raw internal exceptions to users.

## Recommendation progress

Progress updates are append-only history. The current status is the newest entry for each recommendation. The report endpoint includes the latest progress records in `recommendation_progress`.

- Status values: `not_started`, `in_progress`, `completed`, `on_hold`.
- Optional `note`: up to 1,000 characters.
- Optional `measured_value`: finite numeric KPI measurement; use `null`/omit when unknown.
- Optional `due_date`: ISO date (`YYYY-MM-DD`).
- Each update must reference a recommendation ID belonging to that analysis.

## Dependencies

`backend/requirements.txt` already includes `python-multipart` (required for multipart file uploads), `pandas`, `numpy`, and `scikit-learn`. The development requirements in `backend/requirements-dev.txt` include `pytest`, `jsonschema`, and `httpx`.

The project dependency is named `httpx`, not `httpx2`. If a local environment prints an `httpx2` warning, it is not a package declared in these requirements; do not add an `httpx2` dependency solely to silence that message without identifying which tool emitted it.

## Local verification

From `backend/`:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
alembic upgrade head
```

Set `DATABASE_URL` to a dedicated PostgreSQL database before migration/database tests. The database tests drop and recreate tables, so never point them at a database containing data you need.

For the analytics engine's synthetic scenario demos, from the repository root:

```bash
python scripts/run_demo.py --scenario retail --summary
python scripts/run_demo.py --scenario service --check-schema
python scripts/run_demo.py --scenario cold_start --pretty
python scripts/run_demo.py --scenario messy --pretty
python scripts/check_samples.py
```
