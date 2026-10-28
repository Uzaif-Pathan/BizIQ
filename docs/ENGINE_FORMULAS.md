# BizIQ analytics engine — formula reference (Person 2)

Conventions: money in INR; months `YYYY-MM`; percentages are percent numbers (23.29 = 23.29 %);
missing = `null`, **never 0**. A metric that cannot be computed has `value: null` and a `reason`.
Every metric always appears in the output, so consumers can rely on the keys.

## Financial metrics (`analytics_engine/financial`)

| Metric key | Formula | Computed only when |
|---|---|---|
| `revenue` | sum of monthly revenue | at least one month has revenue; months without a value are skipped (noted), not counted as 0 |
| `avg_monthly_revenue` | revenue / months with revenue | as above |
| `months_of_data` | count of months with a revenue value | always |
| `expenses` | sum of monthly **listed** expenses | at least one month has expenses |
| `revenue_minus_listed_expenses` | sum(revenue − expenses) over months with both | both exist; always labelled "not profit unless all expenses are listed" |
| `expense_to_revenue_pct` | listed expenses / revenue × 100 (months with both) | revenue total > 0 |
| `profit` | revenue − expenses over months where `expenses_complete` is true | those months exist; otherwise null with reason "Expense definition incomplete…" |
| `profit_margin_pct` | profit / revenue × 100 (same months as profit) | profit exists and revenue > 0 |
| `revenue_mom_pct`, `expenses_mom_pct` | (latest − previous calendar month) / previous × 100 | previous calendar month exists and is > 0 |
| `revenue_yoy_pct`, `expenses_yoy_pct` | (latest − same month last year) / same month last year × 100 | that month exists and is > 0 |
| `revenue_trend_pct_per_month`, `expenses_trend_pct_per_month` | OLS slope of monthly value on calendar month ÷ mean × 100 | ≥ 4 months and a positive mean |
| `revenue_volatility_cv_pct` | sample std dev / mean × 100 | ≥ 3 months and a positive mean |

Trend direction (`direction`): `flat` if |slope| < 0.5 % of the mean per month; else `unclear`
if R² < 0.25; else `increasing` / `decreasing`. Calendar gaps are respected (x = calendar month,
not row number).

Profit rule: profit is never inferred from an incomplete expense list. If only some months are
marked complete, profit and margin use just those months and say so in `note`.

Months flagged by validation (`needs_review`: negative or extreme values) stay in the
calculations, and every metric they feed carries a `note` saying so.

Thresholds live in `financial/formulas.py` (`MIN_TREND_POINTS`, `FLAT_THRESHOLD_PCT`,
`MIN_TREND_R2`, `MIN_CV_POINTS`) and `constants.py`.

<!-- Later steps append: customer/product analytics, K-Means, forecast, health score, recommendations -->
