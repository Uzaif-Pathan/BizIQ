# BizIQ shared contracts

These files are the only thing the frontend, analytics engine and API must agree on.

- `analysis-result.schema.json`: JSON Schema (draft 2020-12) for the **API contract**: what the API returns and the frontend shows.
- `engine-result.schema.json`: the analytics engine's **native** output. `analytics_engine.api_adapter` converts it to the API contract.
- `examples/analysis-result.completed.example.json`: a completed run with one finding and one recommendation.
- `examples/analysis-result.failed.example.json`: a failed run (all metrics null, error message set).

The Python version of the same contract is `backend/app/schemas/analysis.py`.
If you change one, change the other and tell the team.

## Rules
- Money is a number in INR, never a formatted string such as "₹25,000".
- Percentages are numbers in percent (23.29 means 23.29 %).
- A metric that cannot be calculated is `null`, never `0`.
- `pending` and `failed` runs still return all eight core fields:
  metrics all null, empty `findings` and `recommendations`,
  `evidence_level: "insufficient"`, `benchmark_status: "unavailable"`.
  A `failed` run must also set `error_message`.
- Every recommendation lists the `supporting_finding_ids` that triggered it.
- Business ids and analysis ids are strings in JSON. Real business ids are whole numbers sent as text (for example "42"); analysis ids are text too. The samples use readable ids.

## Core fields
`analysis_id`, `business_id`, `status`, `metrics`, `findings`, `recommendations`,
`evidence_level`, `benchmark_status`.

Optional extras: `method_version`, `limitations`, `error_message`, `created_at`, `completed_at`.

## Allowed values
- `status`: pending, completed, failed
- `evidence_level`: insufficient, low, medium, high
- `benchmark_status`: available, partial, unavailable
- finding `category`: financial, customer, product, trend, benchmark, data_quality
- finding `severity`: info, warning, critical
- recommendation `priority`: high, medium, low
- recommendation `expected_direction`: increase, decrease, maintain (or null)

## Extra optional fields (engine-backed)
`limitations` (why the result is limited), `engine_status` (`completed` / `partial` / `failed`; a `partial` run is still
`status: "completed"`), `error_code`, `metric_details`, `health_score`, `models`, `validation`, `data_coverage`, `series`; per
recommendation: `supporting_metric`, `rule_id`, `caveat`.

## Keeping the two definitions in sync
`backend/app/schemas/analysis.py` and `analysis-result.schema.json` must agree. The test
`test_json_schema_and_pydantic_agree` (analytics_engine/tests/test_api_adapter.py) applies the same valid and invalid edits
to both and fails if they disagree. `examples/` are validated by `test_contract_examples.py`.

## Analytics rules
Metric formulas: `docs/ENGINE_FORMULAS.md`. Evidence level, health score, segmentation, forecast and recommendations:
`backend/analytics_engine/README.md`.
