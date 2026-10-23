# BizIQ shared contracts

These files are the only thing the frontend, analytics engine and API must agree on.

- `analysis-result.schema.json`: JSON Schema (draft 2020-12) for one analysis result.
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
- Business ids and analysis ids in real data are UUID strings. The samples use readable ids.

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

## Still to be documented by the analytics owner
Exact metric formulas and the rules that decide `evidence_level`.
