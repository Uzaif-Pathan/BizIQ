# BizIQ API routes (v1)

Base URL for a local development server: `http://127.0.0.1:8000`.

- Interactive OpenAPI docs: `/docs`
- ReDoc: `/redoc`
- Versioned API prefix: `/api/v1`
- Health endpoints: `/health` and `/api/v1/health`

The examples below use `{business_id}` for a numeric database ID and `{analysis_id}` for the public analysis ID. Although database IDs are integers internally, **IDs in JSON request/response bodies are serialized as strings** by the `EntityId` schema. Do not parse them as floating-point numbers.

## Route index

### Health

| Method | Route | Success response | Notes |
| --- | --- | --- | --- |
| `GET` | `/health` | Health/status object | Unversioned liveness endpoint. |
| `GET` | `/api/v1/health` | Health/status object | Versioned equivalent. |

### Businesses

| Method | Route | Success response | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/v1/businesses` | `BusinessRead`, `201` | Create a business from a JSON `BusinessCreate` body. |
| `GET` | `/api/v1/businesses?limit=50&offset=0` | `BusinessRead[]` | Newest first. `limit` is 1–200; `offset` is at least 0. |
| `GET` | `/api/v1/businesses/{business_id}` | `BusinessRead` | `404` if not found. |
| `PATCH` | `/api/v1/businesses/{business_id}` | `BusinessRead` | Partial update; supports fields such as `goals`. `404` if not found. |

`BusinessRead` includes the public `id`, business profile fields, goals, timestamps, and latest analysis status. See `backend/app/schemas/business.py` for the exact fields and validation.

### Analyses and reports

| Method | Route | Success response | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/v1/businesses/{business_id}/analyses` | `AnalysisResult`, `201` | Runs analysis synchronously. A run that completes with `status: "failed"` is still returned as a created analysis record. |
| `GET` | `/api/v1/businesses/{business_id}/analyses` | `AnalysisRunSummary[]` | Analysis history, newest first. |
| `GET` | `/api/v1/analyses/{analysis_id}` | `AnalysisResult` | Full shared API-contract result. |
| `GET` | `/api/v1/analyses/{analysis_id}/findings` | `Finding[]` | Findings only. |
| `GET` | `/api/v1/analyses/{analysis_id}/recommendations` | `Recommendation[]` | Recommendations only. |
| `GET` | `/api/v1/analyses/{analysis_id}/report` | `ReportPayload` | Business, analysis, generation timestamp, and latest recommendation progress. Returns `409` unless analysis status is `completed`. |

The analysis result's eight core fields are `analysis_id`, `business_id`, `status`, `metrics`, `findings`, `recommendations`, `evidence_level`, and `benchmark_status`. Metrics that cannot be calculated are `null`, not zero. The exact schema is maintained in `backend/app/schemas/analysis.py` and the shared contract files.

### Benchmarks

| Method | Route | Success response | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/v1/businesses/{business_id}/benchmarks` | `BenchmarkResponse` | Returns source/year/geography context, matched industry/state, levels tried, and notes. If the database is not configured or no matching data exists, returns `status: "unavailable"` with an empty `items` list. `404` if the business does not exist. |

Benchmarks are contextual survey comparisons; they are not treated as business profit margins and are not fed into the analytics calculations.

### CSV imports and validation issues

Upload is multipart form data. The uploaded source file is processed during the request; the original CSV file itself is not retained.

| Method | Route | Success response | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/v1/businesses/{business_id}/imports` | `DataImportRead`, `201` | Multipart fields: `data_type` (`financials`, `customers`, or `products`) and `file` (UTF-8 `.csv`, max 5 MiB). |
| `GET` | `/api/v1/businesses/{business_id}/imports` | `DataImportRead[]` | Import history for the business, newest first. |
| `GET` | `/api/v1/businesses/{business_id}/imports/{import_id}` | `DataImportRead` | One import belonging to that business. |
| `GET` | `/api/v1/businesses/{business_id}/imports/{import_id}/issues?severity=warning&limit=100&offset=0` | `ValidationIssueRead[]` | `severity` is optional (`error` or `warning`); `limit` 1–500; `offset` at least 0. |

Upload limits are enforced by the import service: maximum file size 5 MiB and maximum 50,000 data rows. Files that cannot be read (for example empty, non-UTF-8, too large, or not `.csv`) return a structured `400` or `413`. A CSV that can be read but has no usable rows can still create an import record with `status: "failed"` and its validation issues. Validation issues are capped at 50 row occurrences per issue type to avoid unbounded issue records.

Accepted rows are written to the business's normalized monthly tables only when PostgreSQL is configured. Unknown values remain `NULL`; they are not silently replaced with zero. Negative values that the validator flags as invalid are not treated as real negative business values; review the returned issue details.

### Recommendation progress

| Method | Route | Success response | Notes |
| --- | --- | --- | --- |
| `POST` | `/api/v1/analyses/{analysis_id}/recommendations/{recommendation_id}/progress` | `ProgressRead`, `201` | Adds a progress-history entry. |
| `GET` | `/api/v1/analyses/{analysis_id}/recommendations/{recommendation_id}/progress` | `ProgressRead[]` | History for one recommendation, newest first. |
| `GET` | `/api/v1/analyses/{analysis_id}/progress` | `ProgressRead[]` | Latest update per recommendation that has at least one update. Recommendations never updated are omitted. |

The POST JSON body requires `status`: `not_started`, `in_progress`, `completed`, or `on_hold`. Optional fields are `note` (up to 1,000 characters), `measured_value` (finite number; omit or use `null` when unknown), and `due_date` (`YYYY-MM-DD`). The recommendation ID must match one in that analysis. The report payload includes the latest progress updates.

## IDs and error responses

Database primary keys are integer types in PostgreSQL, but public IDs in JSON are strings. For example:

```json
{
  "business_id": "42",
  "analysis_id": "analysis-abc123"
}
```

All handled errors use this envelope:

```json
{
  "error": {
    "code": "not_found",
    "message": "Business not found.",
    "details": null
  }
}
```

`details` may be `null` or a list of field-level validation details. Request validation errors use `422` and `code: "validation_error"`; each detail can include `field`, `message`, and `type`. Other common codes include `bad_request`, `not_found`, `conflict`, `database_unavailable`, and `internal_error`. Unhandled server errors are logged internally and return a sanitized `500` response; stack traces are not sent to API clients.

Common status codes:
- `201`: resource created, including analysis/import/progress operations.
- `400`: malformed or unsupported request/file.
- `404`: business, analysis, import, or recommendation not found.
- `409`: report requested for an analysis that has not completed.
- `413`: uploaded file exceeds size/row limits.
- `422`: request body, query, path, or form validation failed.
- `503`: returned by code paths that require a database session when `DATABASE_URL` is missing; the documented business/analysis/import/progress routes use the optional-memory fallback where supported.

## Storage modes

- **PostgreSQL mode:** set `DATABASE_URL` in the backend environment. Business, analysis, import, normalized imported rows, validation issues, benchmark data, and recommendation progress use SQLAlchemy repositories/tables. Apply Alembic migrations before using the database.
- **In-memory mode:** if `DATABASE_URL` is empty, the app can start for demos and tests. Businesses, analyses, import metadata/issues, and progress live only in process memory and disappear on restart. Crucially, **the in-memory import repository does not retain the accepted financial/customer/product rows**, so an uploaded import cannot feed a later analysis. Benchmark data is unavailable in this mode.

## Run locally

From `backend/`:

```bash
python -m pip install -r requirements-dev.txt
uvicorn app.main:app --reload
```

Set `DATABASE_URL` and run migrations before testing database-backed routes. Do not point the test suite at a database containing data you need: database tests recreate tables.
