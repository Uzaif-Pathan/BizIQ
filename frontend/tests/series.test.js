// Run with:  node --test tests/        (Node 18+, no extra packages needed)
import test from 'node:test';
import assert from 'node:assert/strict';
import {
  num, periodLabel, getSeries, hasFinancialSeries, financialChartRows,
  sumKnown, seriesBounds, latestCustomerValue, endOfMonth,
} from '../src/utils/series.js';

const series = {
  financial_monthly: [
    { period: '2026-03', revenue: 300, expenses: 200, expenses_complete: true, profit: 100, needs_review: false, listed_expenses_exceed_revenue: false },
    { period: '2026-01', revenue: 100, expenses: null, expenses_complete: false, profit: null, needs_review: true, listed_expenses_exceed_revenue: false },
    { period: '2026-02', revenue: null, expenses: 150, expenses_complete: true, profit: null, needs_review: false, listed_expenses_exceed_revenue: true },
  ],
  customer_monthly: [
    { period: '2026-01', active_customers: 40, spend: 1000, transactions: 90 },
    { period: '2026-02', active_customers: 55, spend: null, transactions: null },
    { period: '2026-03', active_customers: null, spend: null, transactions: null },
  ],
  products: [],
};

test('num keeps real numbers (including 0) and nulls everything else', () => {
  assert.equal(num(0), 0);
  assert.equal(num(12.5), 12.5);
  for (const bad of [null, undefined, NaN, Infinity, '5', {}]) assert.equal(num(bad), null);
});

test('periodLabel', () => {
  assert.equal(periodLabel('2026-05'), 'May');
  assert.equal(periodLabel('2026-13'), '2026-13');
  assert.equal(periodLabel('nonsense'), 'nonsense');
  assert.equal(periodLabel(null), '');
});

test('getSeries returns null when absent so the page can show its placeholder', () => {
  assert.equal(getSeries(null), null);
  assert.equal(getSeries({}), null);
  assert.equal(getSeries({ series: null }), null);
  assert.equal(getSeries({ series }), series);
  assert.equal(hasFinancialSeries(null), false);
  assert.equal(hasFinancialSeries({ financial_monthly: [] }), false);
  assert.equal(hasFinancialSeries(series), true);
});

test('financialChartRows sorts by period and keeps null as null (never 0)', () => {
  const rows = financialChartRows(series);
  assert.deepEqual(rows.map((r) => r.period), ['2026-01', '2026-02', '2026-03']);
  assert.equal(rows[0].expenses, null);
  assert.equal(rows[1].revenue, null);
  assert.equal(rows[0].profit, null);
  assert.equal(rows[0].needsReview, true);
  assert.equal(rows[1].expensesExceedRevenue, true);
  assert.equal(rows[0].month, 'Jan');
});

test('financialChartRows filters by inclusive month range', () => {
  assert.deepEqual(financialChartRows(series, '2026-02-15', '2026-03-01').map((r) => r.period), ['2026-02', '2026-03']);
  assert.deepEqual(financialChartRows(series, '2026-04-01', '2026-06-30'), []);
  assert.equal(financialChartRows(null).length, 0);
});

test('sumKnown ignores nulls but reports how many were missing', () => {
  const rows = financialChartRows(series);
  assert.deepEqual(sumKnown(rows, 'revenue'), { total: 400, missing: 1, count: 3 });
  assert.deepEqual(sumKnown(rows, 'expenses'), { total: 350, missing: 1, count: 3 });
  assert.deepEqual(sumKnown([{ revenue: null }], 'revenue'), { total: null, missing: 1, count: 1 });
  assert.deepEqual(sumKnown([{ revenue: 0 }], 'revenue'), { total: 0, missing: 0, count: 1 });
});

test('seriesBounds and endOfMonth', () => {
  assert.deepEqual(seriesBounds(series), { first: '2026-01', last: '2026-03' });
  assert.equal(seriesBounds(null), null);
  assert.equal(endOfMonth('2026-02'), '2026-02-28');
  assert.equal(endOfMonth('2028-02'), '2028-02-29');
  assert.equal(endOfMonth('bad'), '');
});

test('latestCustomerValue skips months with no value', () => {
  assert.deepEqual(latestCustomerValue(series), { period: '2026-02', value: 55 });
  assert.equal(latestCustomerValue({ customer_monthly: [] }), null);
  assert.equal(latestCustomerValue(null), null);
});
