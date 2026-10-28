# BizIQ analytics engine (Person 2)

Standalone Python package. No FastAPI or PostgreSQL needed.

## Run the tests
    pip install pandas numpy scikit-learn pytest
    cd backend && python -m pytest analytics_engine/tests -q

## Regenerate the synthetic sample data
    python scripts/generate_demo_data.py      # writes data/samples/

## Status
- [x] Step 1: validation (`analytics_engine/validation`), sample data, JSON contract schema
- [x] Step 2: financial metrics
- [x] Step 3: customer / product analytics
- [x] Step 4a: K-Means customer segmentation (`analytics_engine/ml/segmentation.py`)
- [x] Step 4b: revenue forecast with held-out evaluation (`analytics_engine/ml/forecast.py`)
- [x] Step 5: explainable health score (`analytics_engine/scoring/health_score.py`)
- [x] Step 6: rule-based recommendations (`analytics_engine/recommendations`)
- [x] Step 7a: `run_analysis` (`pipeline.py`) and evidence level (`evidence.py`)
- [x] Step 7b: CLI demo, contract/schema checks, integration notes for Person 3\n- [x] Part 2: all-scenario verification utility and regression checks\n- [x] Part 3: readable CLI summary for classroom demonstrations\n- [x] Part 4: final handoff guide and repository-level README

## K-Means customer segmentation (`ml/segmentation.py`)
`segment_customers(clean_customers_df) -> {"status", "mae", "rmse", "details"}` (the contract `model` object).
- Features per customer over the latest 12 months: recency (months since last purchase), frequency
  (active months), log(1 + total spend); z-score scaled; zero-variance features dropped.
- Runs only with >= 20 customers and >= 3 months. k in 2..5 chosen by best silhouette score;
  every cluster must hold >= 5 % of customers (and >= 3).
- Evaluation gate: silhouette >= 0.25, otherwise status `skipped_insufficient_data` with
  `details.skip_code = "weak_structure"` and no segments are returned. Stability (ARI across two
  seeds) is reported. Deterministic (`random_state=42`).
- Segment names (Loyal high-value, Lapsed / inactive, ...) are rule-based labels on the cluster
  averages, not model output.
- `status`: `ok`, `skipped_insufficient_data` (see `details.skip_code`: too_few_customers,
  too_few_months, no_variation, no_valid_k, weak_structure), `not_applicable` (no customer data),
  or `failed` (never raises).

## Revenue forecast (`ml/forecast.py`)
`forecast_revenue(clean_financials_df, horizon=3) -> {"status", "mae", "rmse", "details"}` (contract `model` object;
`mae`/`rmse` are the held-out scores).
- Needs >= 9 months with revenue (6 to train + 3 held out) and a positive average. Missing months are ignored
  (never zero-filled); the calendar month is the x axis so gaps are respected.
- Candidates: `naive` (repeat last month), `moving_average_3`, `linear`. The last 3 observed months are held out;
  each candidate is scored (MAE, RMSE, MAPE). Lowest MAE wins, ties go to the simpler model.
- Reliability gate: holdout MAPE must be <= 25 %. Otherwise status is `skipped_insufficient_data` with
  `details.skip_code = "poor_accuracy"`: the evaluation is reported but no future values are shown.
- `details.beats_naive` says whether the winner beat "repeat last month"; if not, `details.caveat` says the forecast is
  effectively flat. `low`/`high` = forecast -/+ holdout RMSE (a typical error, not a confidence interval).
- `skip_code` values: too_few_months, non_positive_revenue, poor_accuracy. `not_applicable` = no financial data.
  Never raises (`failed` instead). Horizon 1..6 months, default 3.

## Health score (`scoring/health_score.py`)
`compute_health_score(fin, cus, pro, benchmarks=None) -> health_score object`, where `fin`, `cus`, `pro` are the results of
`analyze_financials`, `analyze_customers`, `analyze_products` (any may be None). It is a 0-100 summary of fixed rules,
**not a probability of business success** (`disclaimer` says so).

| Component | Base weight | Indicator | Basis |
|---|---|---|---|
| profitability | 25 | profit_margin_pct (needs complete expenses) | `benchmark` if a matching benchmark is passed, else `measured` |
| growth | 20 | 12-month growth, else YoY, else a clear revenue trend (annualised) | measured |
| cost_control | 15 | expenses YoY minus revenue YoY (percentage points) | measured |
| revenue_stability | 10 | coefficient of variation of monthly revenue (>= 6 months) | rule |
| customer_loyalty | 10 | repeat-customer rate and monthly retention | measured |
| customer_concentration | 10 | largest customer / top 10 % share (>= 5 customers) | rule |
| product_margin | 5 | gross margin (minus 10 pts per loss-making product, max 20); benchmark if supplied | measured / benchmark |
| product_concentration | 5 | best-selling product share (>= 3 products) | rule |

- `measured` = scored from an outcome in the business's own records; `rule` = generic rule-of-thumb threshold on a
  structural indicator (not an industry benchmark); `benchmark` = compared with a supplied benchmark (source, year and
  geography level are recorded on the component). Only benchmarks whose `metric` matches exactly are used.
- Each indicator is mapped to 0-100 points by a piecewise-linear curve (`CURVES` in the module). Unavailable components are
  listed in `unavailable_components` with the reason in `limitations`; their weight is redistributed over the available
  ones (`weight` = effective %, `base_weight` = fixed).
- A score is only produced when at least one financial outcome (profitability, growth, cost control) is available **and**
  available components cover >= 40 % of the base weight. Otherwise `score` is null and `limitations` explains why; the
  components that could be computed are still listed (unweighted).
- Explanation: each component has `points`, `effect_points` = weight/100 x (points - 50) (score = 50 + sum of effects),
  `direction` (raises >= 65, lowers <= 40) and a plain-language `explanation`. `raised_by` / `lowered_by` name the main
  drivers. `band`: strong >= 75, moderate >= 55, weak >= 35, else at risk.

## Recommendations (`recommendations/`)
`build_recommendations(findings, business_type=None, evidence_level=None) -> list[recommendation]`, where `findings` is the
combined list from `build_financial_findings`, `build_customer_findings` and `build_product_findings`. No external LLM.
- Rules live in `recommendations/rules.py` (one `Rule` per row: finding types -> issue, action per business type, KPI,
  expected direction). A rule fires only if one of its finding types is present with severity above `info`; related
  findings are grouped into one recommendation (e.g. low margin + loss months -> `REC-LOSS`).
- Every recommendation has `finding_ids` (>= 1, strongest first), `issue`, `supporting_metric`, `evidence` (the findings'
  own evidence text), `action`, `priority`, `kpi`, `rationale` (which rule, which findings, "not a guaranteed result") and
  `expected_direction` (`{metric, direction}`: the direction we aim for, not a forecast; `null` for data-quality actions:
  complete the expense list, fix flagged records, widen data coverage).
- Priority = highest severity among the findings (high / medium / low). Output sorted high -> low, then rule order.
- `retail` and `service` get tailored wording; any other value uses the generic `other` wording.
- `evidence_level == "low"` adds a `caveat` to each recommendation.
- Healthy businesses can legitimately get an empty list. A test checks that every rule listens to a finding type that a
  findings builder really produces, so a renamed finding type cannot silently disable a rule.

## Entry point: `run_analysis` (`pipeline.py`)
    from analytics_engine import run_analysis
    result = run_analysis(business, {"financials": df, "customers": df_or_None, "products": df_or_None}, benchmarks=None)

- Validates every provided table, then runs financial / customer / product analytics, findings, recommendations, the
  health score, segmentation and the forecast, and returns one JSON-safe dict (no NaN, no numpy types).
- **Never raises.** Bad input gives `status: "failed"` with `error.code` (`invalid_input`, `no_usable_data`,
  `internal_error`). A step that crashes is skipped, recorded as a `module_failed` warning, and the result is `partial`.
- `status`: `completed` (every provided table valid, financials usable, no step failed); `partial` (any validation error,
  an unusable table, no usable financials, or a failed step); `failed` (nothing usable).
- Without a usable financial table but with customer/product data the result is `partial` with `evidence_level: low`
  and no health score. Optional tables that are absent are not errors.
- Extra top-level fields beyond the schema's required ones: `evidence_notes` (why the level is what it is),
  `data_coverage`, `business_type` (normalised), `validation.datasets` (rows in/out per table), `engine_version`.
- `benchmark_status`: `available` = every benchmarkable metric computed (`profit_margin_pct`, `gross_margin_pct`) was
  compared with a supplied benchmark of the same `metric`; `partial` = some; `unavailable` = none.

## Evidence level (`evidence.py`)
| Level | Rule |
|---|---|
| high | >= 12 months with revenue, no validation errors in the financial table, and a usable, error-free customer or product table |
| medium | 6-11 months; or >= 12 months of financials only; or >= 12 months but the financial table had errors (rows excluded) |
| low | < 6 months with revenue, or no usable financial table |

It describes the data behind the result, not the business. Low evidence adds a caveat to every recommendation.


## Step 7b: CLI demo and integration

From the repository root:

```bash
pip install -r requirements-dev.txt
python scripts/run_demo.py --scenario retail --summary
python scripts/run_demo.py --scenario retail --pretty --output output/retail-analysis.json --check-schema
python scripts/run_demo.py --scenario service --check-schema
python scripts/run_demo.py --scenario cold_start --pretty
python scripts/run_demo.py --scenario messy --pretty
```

The demo uses only synthetic data. `--check-schema` validates the JSON result against
`contracts/analysis-result.schema.json` (install `jsonschema` for this optional check).
Person 3's adapter contract and dataset expectations are documented in `docs/PERSON3_INTEGRATION.md`.


### Verify every bundled scenario

```bash
python scripts/check_samples.py
```

This runs retail, service, cold-start, and intentionally messy synthetic data through
the full pipeline, checks strict JSON serialization, and validates each result against
the output schema.
\nThe `--summary` option prints key metrics, health-score availability, supported findings, recommendations, model statuses, and data-quality warnings in a classroom-demo-friendly format. The JSON output remains the integration contract.\n