# BizIQ analytics engine: integration notes for Person 3

## Single entry point

Call `analytics_engine.run_analysis(business, data, benchmarks=None)` from the backend adapter. The engine is deliberately independent of FastAPI and PostgreSQL.

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

The engine does not open files, connect to a database, or make network calls. The adapter should fetch authorized rows, convert each dataset to a DataFrame, and pass the frames to this function. Persist the returned JSON-safe dict as the analysis result.

## Dataset expectations

- Financials: one row per business/month; `business_id`, `period` (`YYYY-MM` or parseable date), `revenue`; `expenses` and `expenses_complete` when available.
- Customers: customer-period activity with `business_id`, `period`, `customer_id`, `transactions`, `amount_spent`.
- Products: product-period data with `business_id`, `period`, `product_id`, `product_name`, `units_sold`, `revenue`, `cost`.
- Each table is optional. Missing tables reduce coverage and may cause individual models or metrics to be marked unavailable; do not fabricate empty zero-valued records.
- Keep money in INR and periods in a consistent calendar-month representation. Apply business/user authorization before querying data; never trust a `business_id` supplied by an untrusted client without checking ownership.

## Two formats, one adapter

`run_analysis` returns the engine's **native** result (`contracts/engine-result.schema.json`): metrics are objects
(`value`, `unit`, `period`, `formula`, `reason`), findings use `id`/`type`/`evidence`, recommendations use
`id`/`finding_ids`/`rationale`.

The API and frontend use the **API contract** (`contracts/analysis-result.schema.json`, mirrored by
`backend/app/schemas/analysis.py`): flat metrics, `finding_id`/`category`/`title`/`description`, recommendations with
`supporting_finding_ids`/`reason`. `analytics_engine/api_adapter.py` converts one into the other, so no route, model or
frontend file has to change.

| Native | API contract |
|---|---|
| `metrics.revenue = {"value": 5, ...}` | `metrics.revenue = 5` (null stays null); `profit_margin_pct` is exposed as `profit_margin`; unit/period/formula/reason kept in `metric_details` |
| finding `id`, `type`, `metric`, `value`, `evidence` (text), `comparison` | `finding_id`, readable `title` + `category`, `metric_name`, `metric_value`, `description`, `evidence` (list) |
| severity info / low / medium / high | info / info / warning / critical |
| recommendation `id`, `finding_ids`, `rationale`, `expected_direction` `{metric, direction}` | `recommendation_id`, `supporting_finding_ids`, `reason`, `expected_direction` as a string or null |
| status `completed` / `partial` / `failed` | `completed` (raw value in `engine_status`, explained in `limitations`) / `completed` / `failed` + `error_message` |
| evidence level low / medium / high | same; failed runs get `insufficient` |

Extra optional fields the API result carries (add them to the Pydantic model when the frontend needs them, otherwise
FastAPI will drop them): `limitations`, `engine_status`, `error_code`, `metric_details`, `health_score`, `models`,
`validation`, `data_coverage`, `series` (chart rows: `financial_monthly`, `customer_monthly`, `products`; missing values are null, never 0; no customer ids), and per-recommendation `supporting_metric`, `rule_id`, `caveat`.

- Metrics: a `null` means unavailable and must not be shown as zero; `metric_details[key].reason` says why.
- `health_score` is a transparent rule-based indicator, not a probability of success or a credit rating.
- `models.segmentation` and `models.forecast` report status and evaluation, and omit predictions when quality gates fail.
- `evidence_level` rules and every formula are in `docs/ENGINE_FORMULAS.md` and `backend/analytics_engine/README.md`.

## Wiring the engine into `app/services/analytics_service.py`

This is documentation only; Person 3 owns that file. Replace `mock_engine` like this:

```python
from analytics_engine.api_adapter import run_for_service

def real_engine(business: BusinessRead) -> Dict[str, Any]:
    # Person 3: read this business's stored rows and return DataFrames (None for tables that do not exist).
    data = {"financials": financials_df, "customers": customers_df, "products": products_df}
    return run_for_service(business, data)

def get_analytics_engine() -> AnalyticsEngine:
    return real_engine
```

- `run_for_service` maps the business (`manufacturing` / `hybrid` -> `other`), runs the engine, converts the result and
  removes `analysis_id`, `business_id`, `status` and the timestamps, because `analysis_service.run_analysis` passes
  `**output` next to those (duplicates would raise a TypeError).
- If the engine cannot analyse the data (for example no usable financials) it raises `EngineRunFailed(code, message)`.
  `analysis_service` currently hard-codes `COMPLETED` and turns every exception into a generic failure. To keep the useful
  reason, add before the generic `except`:

```python
    except EngineRunFailed as exc:
        result = _empty_result(analysis_id, business_id, AnalysisStatus.FAILED, created_at,
                               completed_at=_now(), error_message=exc.message)
```

- Known gaps (not engine work): the backend has no repository that supplies financial / customer / product rows yet (only
  business and analysis repositories and the SQLAlchemy models), so `data` has to be loaded by new code. `backend/requirements.txt`
  must also list `pandas`, `numpy`, `scikit-learn` (and `jsonschema` for the schema checks).

## Suggested adapter behaviour

1. Validate the authenticated user's access to the business.
2. Read the selected business and the available datasets from storage.
3. Convert records to pandas DataFrames; pass only columns the user is permitted to analyze.
4. Call `run_analysis` in a worker/thread if analysis may be expensive for your API request path.
5. Persist the JSON result and metadata; return the result to the frontend.
6. Treat validation errors as data-quality feedback, not an application crash. A failed analysis should be surfaced with its error code/message.
7. Avoid returning stack traces or raw internal exceptions to end users. The engine intentionally returns sanitized failure information.
8. Use the schema test or `--check-schema` demo option during integration to catch contract drift.

## Local demo

From the repository root:

```bash
pip install -r requirements-dev.txt
python scripts/run_demo.py --scenario retail --summary
python scripts/run_demo.py --scenario retail --pretty --output output/retail-analysis.json --check-schema
python scripts/run_demo.py --scenario service --check-schema
python scripts/run_demo.py --scenario cold_start --pretty
python scripts/run_demo.py --scenario messy --pretty
python scripts/check_samples.py
```

`retail`, `service`, `cold_start`, and `messy` are synthetic datasets. They contain no real customer records.

## Dependencies to add (Person 3 owns `backend/requirements.txt`)

The engine needs three packages that `backend/requirements.txt` does not list yet:

```
pandas>=2.2,<4
numpy>=1.26,<3
scikit-learn>=1.4,<2
```

For tests, put `pytest`, `jsonschema` and `pydantic` in `backend/requirements-dev.txt` (it is empty today). Also note that
`requirements.txt` currently lists `httpx2`, which looks like a typo for `httpx` (needed by FastAPI's test client); please check.
Copies of these lines are in `backend/analytics_engine/requirements.txt` and `requirements-dev.txt` for reference; the engine does not read them.
