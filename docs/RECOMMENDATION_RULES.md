# Recommendation rules: reasoning and input data

Source of truth: `backend/analytics_engine/recommendations/rules.py` (wording, KPI) and `engine.py` (how a rule fires).
Finding thresholds live in `financial/findings.py`, `customers/findings.py`, `products/findings.py`.
A test (`test_recommendation_docs.py`) fails if a rule exists in code but is missing from this file.

## How a recommendation is produced

1. Validation cleans the uploaded tables. Missing values stay missing; they are never treated as zero.
2. The analysis modules compute metrics (formulas: `ENGINE_FORMULAS.md`) over the latest 12 months with revenue.
3. Finding builders compare metrics with **generic rules of thumb** and give each finding a severity
   (`info`, `low`, `medium`, `high`). These are *not* industry benchmarks; the engine never invents benchmarks.
4. A rule fires only if at least one finding of its listed types has severity above `info`.
5. Each recommendation carries: `rule_id`, `finding_ids` (at least one), `evidence` (the findings' own text, up to 3),
   `supporting_metric`, `kpi`, `expected_direction`, `rationale`, and a `caveat` when the evidence level is `low`.
6. Priority = highest severity among the triggering findings (high/medium/low). Output is sorted by priority, then rule order.
7. Wording depends on business type (retail, service, anything else = generic).

`expected_direction` is the direction we aim for, not a forecast. It is `null` for data-quality rules, because completing
data does not move a business metric. Nothing here promises a business outcome.

## Rules

| Rule | Fires on finding types | Input data needed | Aim (metric, direction) | KPI to watch |
|---|---|---|---|---|
| EXPENSE-LIST | `expense_definition_incomplete` | financials (revenue, expenses, `expenses_complete`) | none (data quality) | Whether profit can be calculated |
| LOSS | `profit_margin_level`, `loss_months` | financials with complete expenses (margin) or listed expenses (loss months) | `profit_margin_pct` increase | Profit margin %, months with costs above revenue |
| COSTS | `expenses_outpacing_revenue` | financials, at least 6 months (`MIN_TREND_POINTS`), clear trends (R² at least 0.3) | `listed_expenses_trend_pct_per_month` decrease | Expense growth minus revenue growth |
| REVENUE-DECLINE | `revenue_decline_yoy`, `revenue_trend_decreasing`, `revenue_decline_mom`, `revenue_growth_12m` | financials, 13+ months for year-on-year | `revenue_yoy_pct` increase | Revenue vs same month last year |
| VOLATILITY | `revenue_volatility` | financials, 6+ non-flagged months | `revenue_cv` decrease | Month-to-month variation |
| CUSTOMER-RETENTION | `repeat_customers_low`, `customer_retention_low` | customers (customer_id, period) | `repeat_customer_rate_pct` increase | Repeat rate %, monthly retention % |
| CUSTOMER-DECLINE | `active_customers_decreasing` | customers, at least 6 months | `active_customers_trend_pct_per_month` increase | Active customers per month |
| CUSTOMER-CONCENTRATION | `customer_concentration` | customers, at least 5 customers | `top_customer_share_pct` decrease | Largest customer's share of spend |
| PRODUCT-MARGIN | `negative_margin_product`, `low_margin_main_product` | products with cost | `gross_margin_pct` increase | Gross margin of named products |
| PRODUCT-CONCENTRATION | `product_concentration` | products, at least 2 products | `top_product_share_pct` decrease | Best seller's share of revenue |
| PRODUCT-DECLINE | `product_revenue_declining`, `product_losing_share` | products, at least 6 months | `revenue_trend_pct_per_month` increase | Monthly revenue of named products |
| LOW-CONTRIBUTION | `low_contribution_products` | products, at least 5 products | `products_below_5pct_share` decrease | Products under 5% of revenue |
| DATA-COVERAGE | `customer_data_coverage_low`, `product_data_coverage_low` | customers or products plus financials | none (data quality) | Share of revenue covered by records |
| DATA-REVIEW | `data_needs_review` | any table with flagged rows | none (data quality) | Number of flagged records |

## What makes each finding fire (generic rules of thumb)

| Finding type | Severity logic |
|---|---|
| `profit_margin_level` | margin < 0% high; < 5% medium; < 10% low; otherwise info. Only when expenses are marked complete |
| `expense_definition_incomplete` | medium whenever profit cannot be computed (expense list not complete) |
| `loss_months` | months where listed expenses exceed revenue: 3 or more high, 1 to 2 medium |
| `revenue_trend_decreasing` | slope below -2% per month high; below -0.5% medium |
| `revenue_decline_yoy` | latest month 10% or more below same month last year: medium; 25% or more: high |
| `revenue_decline_mom` | latest month 15% or more below the previous: low (may be seasonal) |
| `revenue_growth_12m` | medium only if last 12 months are 10% or more below the 12 before; otherwise info |
| `expenses_outpacing_revenue` | expense trend minus revenue trend above 0.5 pp per month: medium; 2 pp or more: high |
| `revenue_volatility` | std / mean of the last up to 12 months at least 0.25: low |
| `repeat_customers_low` | under 25% of customers buy in 2+ months: medium |
| `customer_retention_low` | average monthly retention under 25% high; under 40% medium |
| `customer_concentration` | largest customer 25% or more, or top 10% of customers 70% or more: high; 15% / 50% / top 5 at 60%: medium |
| `active_customers_decreasing` | decreasing trend with a clear fit: medium |
| `negative_margin_product` | gross margin below 0%: high |
| `low_margin_main_product` | margin under 10% and share 15% or more: medium |
| `product_concentration` | top product 60% or more high; 40% or more medium |
| `product_revenue_declining`, `product_losing_share` | medium if the product is 10% or more of revenue, else low; at most 3 products |
| `low_contribution_products` | 5+ products and 2 or more under 5% share: low |
| `*_data_coverage_low` | records cover under 50% of financial revenue: low |
| `data_needs_review` | flagged financial months: medium; flagged customer rows: low |

## Reading a recommendation: worked example

Messy sample (`data/samples/messy`, 12 months, business type `other`):

* Finding `FIN-EXPDEF` (medium): expenses are not marked complete, so profit is not reported; revenue minus listed expenses is INR 1,425,000.
  Rule `EXPENSE-LIST` fires, priority medium, `expected_direction` null.
* Finding `FIN-REVIEW` (medium): 2 months have unusual values that were kept but flagged. Rule `DATA-REVIEW` fires.

The service sample produces only `REC-EXPENSE-LIST` for the same reason. The retail sample (complete expenses, 21.8% margin, growing
revenue) produces only `REC-PRODUCT-DECLINE`, triggered by `PRD-DECLINE-P04` (medium) and `PRD-DECLINE-P06` (low): two products with falling
revenue. Healthy headline metrics raise no profit or revenue recommendation: the engine does not invent problems.

## Limits

* Thresholds are generic rules of thumb chosen for transparency. They are not industry benchmarks and may not suit every business.
* A `low` evidence level (fewer than 6 months of data, or many rows removed) adds a caveat to every recommendation.
* Seasonality is not modelled; the text says so where it matters.
