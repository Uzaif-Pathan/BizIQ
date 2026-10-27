// Helpers for the engine's `series` block (analysis.series).
// Rule for every helper here: a null / missing / non-numeric value stays null.
// It is NEVER turned into 0, so charts show a gap and sums say how much was missing.

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

// number | null. Accepts only finite numbers; strings, NaN, Infinity, undefined -> null.
export function num(v) {
  return typeof v === 'number' && Number.isFinite(v) ? v : null;
}

// 'YYYY-MM' -> 'May'. Anything else is returned unchanged (or '' when missing).
export function periodLabel(period) {
  const m = /^(\d{4})-(\d{2})$/.exec(String(period ?? ''));
  if (!m) return period == null ? '' : String(period);
  const name = MONTHS[Number(m[2]) - 1];
  return name ?? String(period);
}

export function getSeries(analysis) {
  const s = analysis?.series;
  return s && typeof s === 'object' ? s : null;
}

export function hasFinancialSeries(series) {
  return Array.isArray(series?.financial_monthly) && series.financial_monthly.length > 0;
}

export function hasCustomerSeries(series) {
  return Array.isArray(series?.customer_monthly) && series.customer_monthly.length > 0;
}

// 'YYYY-MM-DD' or 'YYYY-MM' -> 'YYYY-MM' (or null when unusable).
function monthOf(dateStr) {
  const m = /^(\d{4}-\d{2})/.exec(String(dateStr ?? ''));
  return m ? m[1] : null;
}

// Rows for the revenue/expenses chart, oldest first, optionally limited to a date range.
// Both bounds are inclusive and compared by month, so '2026-05-15' includes all of May.
export function financialChartRows(series, from, to) {
  if (!hasFinancialSeries(series)) return [];
  const lo = monthOf(from);
  const hi = monthOf(to);
  return series.financial_monthly
    .filter((r) => r && typeof r.period === 'string')
    .filter((r) => (!lo || r.period >= lo) && (!hi || r.period <= hi))
    .map((r) => ({
      period: r.period,
      month: periodLabel(r.period),
      revenue: num(r.revenue),
      expenses: num(r.expenses),
      profit: num(r.profit),
      expensesComplete: r.expenses_complete === true,
      needsReview: r.needs_review === true,
      expensesExceedRevenue: r.listed_expenses_exceed_revenue === true,
    }))
    .sort((a, b) => (a.period < b.period ? -1 : a.period > b.period ? 1 : 0));
}

// Sums only the known values. `total` is null when nothing was known, so the UI can show '—'.
export function sumKnown(rows, key) {
  let total = null;
  let missing = 0;
  for (const r of rows) {
    const v = num(r?.[key]);
    if (v === null) missing += 1;
    else total = (total ?? 0) + v;
  }
  return { total, missing, count: rows.length };
}

// First and last period in the financial series, e.g. { first: '2026-01', last: '2026-06' }.
export function seriesBounds(series) {
  const rows = financialChartRows(series);
  return rows.length ? { first: rows[0].period, last: rows[rows.length - 1].period } : null;
}

// Last month that has a known value for `key` in customer_monthly.
export function latestCustomerValue(series, key = 'active_customers') {
  if (!hasCustomerSeries(series)) return null;
  const rows = series.customer_monthly
    .filter((r) => r && typeof r.period === 'string' && num(r[key]) !== null)
    .sort((a, b) => (a.period < b.period ? -1 : 1));
  const last = rows[rows.length - 1];
  return last ? { period: last.period, value: num(last[key]) } : null;
}

// Last calendar day of 'YYYY-MM' as 'YYYY-MM-DD' (for date inputs).
export function endOfMonth(period) {
  const m = /^(\d{4})-(\d{2})$/.exec(String(period ?? ''));
  if (!m) return '';
  const day = new Date(Number(m[1]), Number(m[2]), 0).getDate();
  return `${period}-${String(day).padStart(2, '0')}`;
}

// ---------- Added for the Financial / Customers / Products / Trends pages ----------

export function hasProductSeries(series) {
  return Array.isArray(series?.products) && series.products.length > 0;
}

// Rows for the customer chart and table, oldest first. Nulls stay null.
export function customerChartRows(series) {
  if (!hasCustomerSeries(series)) return [];
  return series.customer_monthly
    .filter((r) => r && typeof r.period === 'string')
    .map((r) => ({
      period: r.period,
      month: periodLabel(r.period),
      activeCustomers: num(r.active_customers),
      spend: num(r.spend),
      transactions: num(r.transactions),
    }))
    .sort((a, b) => (a.period < b.period ? -1 : a.period > b.period ? 1 : 0));
}

// Product rows for the table, best revenue rank first. Rows without a rank go last.
export function productRows(series) {
  if (!hasProductSeries(series)) return [];
  return series.products
    .filter((r) => r && typeof r === 'object')
    .map((r) => ({
      id: String(r.product_id ?? r.product_name ?? ''),
      name: r.product_name ?? r.product_id ?? 'Unnamed',
      monthsActive: num(r.months_active),
      revenue: num(r.revenue),
      unitsSold: num(r.units_sold),
      cost: num(r.cost),
      grossProfit: num(r.gross_profit),
      grossMarginPct: num(r.gross_margin_pct),
      revenueSharePct: num(r.revenue_share_pct),
      rank: num(r.rank_by_revenue),
    }))
    .sort((a, b) => {
      if (a.rank === null && b.rank === null) return (b.revenue ?? -Infinity) - (a.revenue ?? -Infinity);
      if (a.rank === null) return 1;
      if (b.rank === null) return -1;
      return a.rank - b.rank;
    });
}

// Month-over-month change for `key`. A change is only reported when this month and the previous
// row both have known values; the percent is also null when the previous value is 0 (undefined).
// Rows must already be sorted oldest first (financialChartRows / customerChartRows do that).
export function monthOverMonth(rows, key) {
  return rows.map((r, i) => {
    const value = num(r?.[key]);
    const previous = i > 0 ? num(rows[i - 1]?.[key]) : null;
    const change = value !== null && previous !== null ? value - previous : null;
    const percent = change !== null && previous !== 0 ? (change / Math.abs(previous)) * 100 : null;
    return { period: r.period, month: r.month, value, previous, change, percent };
  });
}
