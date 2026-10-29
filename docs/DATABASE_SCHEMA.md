# BizIQ database schema

BizIQ uses PostgreSQL 16, SQLAlchemy 2 models, and Alembic migrations. The database schema is defined by the ordered migration chain below; do not rely on `create_all()` as a replacement for migrations in a deployed environment.

## Migration history

| Revision | Parent | Purpose |
| --- | --- | --- |
| `48681f5892d3_initial_database_schema` | — | Initial users, businesses, goals, monthly financial/customer/product data, benchmarks, analysis runs, findings, recommendations, reports, and supporting tables. |
| `0002_engine_integration` | `48681f5892d3` | Adds analytics-engine integration fields, nullable/unknown financial values, JSON analysis results, public analysis IDs, recommendation external IDs, import data type, and `customer_activity`. |
| `0003_benchmark_columns` | `0002_engine_integration` | Adds ASUSE benchmark breakdown columns and a lookup index. |

Apply all migrations from the `backend/` directory:

```bash
alembic upgrade head
alembic current
alembic history
```

`DATABASE_URL` must be set to the target PostgreSQL database. Use a dedicated database for tests because the database tests drop and recreate tables.

## Main tables

The initial migration contains the core account/business and analytics tables. Revisions 0002 and 0003 extend that foundation.

| Table | Purpose / important fields |
| --- | --- |
| `app_users` | User records. The current backend uses `DEFAULT_OWNER_USER_ID`/`default_owner_user_id` for demo ownership; authentication and production authorization still need to be enforced by the application. |
| `businesses` | Business profile and location, business type, employee count, and timestamps. Revision 0002 adds `stage` (`new` or `established`) and optional `description`. |
| `business_goals` | Goals associated with a business. |
| `monthly_financials` | One record per business/month. Stores revenue and expense components, investment/capital fields, optional `expenses_complete`, and optional `source_import_id`. Revision 0002 allows revenue and expense components to be `NULL`. |
| `monthly_customer_metrics` | Existing monthly customer aggregate metrics from the initial schema. |
| `customer_activity` | Revision 0002 table: one row per anonymous customer reference per business/month, with optional `transactions` and `amount_spent`, plus `source_import_id`. Unique key: `(business_id, customer_ref, period_start)`. |
| `products_services` | Business-owned product/service catalog. |
| `monthly_product_metrics` | Per-product/month units, revenue, cost and inventory/return metrics. Revision 0002 adds `total_cost` and its non-negative check. |
| `benchmark_sources` | Provenance/source metadata for benchmark datasets. |
| `industry_benchmarks` | Benchmark values by metric, geography, industry, year, and source. Revision 0003 adds `sector`, `establishment_type`, `worker_group`, `industry_scheme`, and `is_rollup`, plus `ix_industry_benchmarks_lookup`. |
| `market_snapshots` | Market/context snapshots defined by the initial schema. |
| `analysis_runs` | Analysis status and metadata. Revision 0002 adds unique `public_id`, `result_json` (JSONB), `benchmark_status`, and `error_message`; `run_status` permits `PENDING`, and `evidence_level` permits `INSUFFICIENT`. |
| `analysis_findings` | Persisted findings associated with an analysis run. |
| `recommendations` | Recommendations associated with an analysis. Revision 0002 adds `external_id`, used to preserve the analytics engine's public recommendation ID, unique per analysis when present. |
| `recommendation_progress` | Append-only progress history for a recommendation: status, note, optional measured value/due date, timestamp and updater. |
| `reports` | Report records associated with analyses. |
| `data_imports` | Import metadata and row counts/status. Revision 0002 adds `data_type` (`FINANCIALS`, `CUSTOMERS`, `PRODUCTS`). The uploaded file bytes are not stored. |
| `validation_issues` | Validation errors/warnings linked to an import; records include row, column, issue type/message, severity, and resolution status. |

Exact columns, constraints, indexes and foreign keys are defined in `backend/app/models/` and `backend/alembic/versions/`.

## Important revision 0002 details

### Preserve unknown financial values

- `monthly_financials.revenue`, `fixed_expenses`, `variable_expenses`, and `other_expenses` may be `NULL`.
- `expenses_complete` is tri-state: `TRUE` means the listed expenses are complete; `FALSE` means they are known to be incomplete; `NULL` means the user did not state whether they are complete.
- The analytics data loader converts unknown values to missing values and does not invent zeros. For expenses, known expense components are summed; if all components are unknown, expenses are unknown.
- The migration's downgrade must replace `NULL` financial components with zero before restoring the old `NOT NULL` constraints. This is lossy, so do not downgrade casually.

### Public analysis IDs and JSON results

- `analysis_runs.analysis_id` is the internal integer primary key.
- `analysis_runs.public_id` is the unique public ID returned by the API as a JSON string.
- `result_json` stores the JSON analysis payload; `benchmark_status` and `error_message` support reporting failures and benchmark state.
- `run_status` allows `PENDING`, `RUNNING`, `COMPLETED`, and `FAILED`.
- `evidence_level` allows `HIGH`, `MEDIUM`, `LOW`, and `INSUFFICIENT`.

### Customer activity

`customer_activity` supports the engine's repeat-customer, concentration and segmentation features. `customer_ref` is an anonymous business-provided reference (for example `C001`), not a customer's name, phone number, email address, or other direct identifier. A business can have one row per `customer_ref` per `period_start`. `transactions` and `amount_spent` can be unknown (`NULL`); `transactions` cannot be negative.

### Import and validation storage

`data_imports` stores metadata only: business, uploader when available, data type, sanitized file name, format/source/status, row counts, and timestamps. The raw uploaded CSV is processed in the request and is not persisted as a file.

- Financial rows are written to `monthly_financials`.
- Customer rows are written to `customer_activity`.
- Product rows are written to `products_services` and `monthly_product_metrics`.
- Each stored normalized row references its source import where supported.
- Validation issues are written to `validation_issues` and cascade-delete with their import.
- Accepted rows are persisted only when PostgreSQL is configured. Invalid/rejected rows are not stored.
- Re-uploading overlapping periods/keys replaces the existing row for the same business/month (and customer or product key); periods not included in the new file are left unchanged.
- Missing numeric values stay `NULL`, never zero. Review warnings before relying on a dataset for an analysis.

Without `DATABASE_URL`, the API uses in-memory repositories. Import metadata and validation issues are available during that process, but **accepted normalized rows are not retained at all**, so an import cannot be used as input to a later analysis. All in-memory records are lost when the process restarts.

## Revision 0003 benchmark fields

`industry_benchmarks` gains:
- `sector` — survey sector such as rural, urban, or combined.
- `establishment_type` — survey establishment grouping such as HWE, OAE, or all.
- `worker_group` — worker/formality grouping.
- `industry_scheme` — the industry classification scheme used for the row.
- `is_rollup` — indicates an aggregated/roll-up benchmark row.

The index `ix_industry_benchmarks_lookup` covers `metric_name`, `geography_level`, `state`, and `industry_name` for benchmark selection.

## Model artifact policy

The repository's `.gitignore` ignores generated files in `model_artifacts/`, including trained model files such as `.joblib`, `.pkl`, and `.pickle`. Only `model_artifacts/README.md` and `model_artifacts/.gitkeep` are intentionally retained. Trained artifacts should be generated locally or through the documented training workflow; do not commit generated model binaries or business/customer data.
