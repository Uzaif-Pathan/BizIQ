import test from 'node:test';
import assert from 'node:assert/strict';
import {
  customerChartRows, productRows, monthOverMonth, hasProductSeries, financialChartRows,
} from '../src/utils/series.js';

test('customerChartRows sorts by period and keeps null as null', () => {
  const rows = customerChartRows({
    customer_monthly: [
      { period: '2026-02', active_customers: null, spend: 50, transactions: 2 },
      { period: '2026-01', active_customers: 10, spend: null, transactions: 0 },
    ],
  });
  assert.deepEqual(rows.map((r) => r.period), ['2026-01', '2026-02']);
  assert.equal(rows[0].spend, null);
  assert.equal(rows[0].transactions, 0);
  assert.equal(rows[1].activeCustomers, null);
});

test('customerChartRows returns [] when the series is absent', () => {
  assert.deepEqual(customerChartRows(null), []);
  assert.deepEqual(customerChartRows({}), []);
});

test('productRows ranks by revenue, unranked last, nulls stay null', () => {
  const rows = productRows({
    products: [
      { product_id: 'c', product_name: 'C', revenue: 5, rank_by_revenue: null, cost: null },
      { product_id: 'b', product_name: 'B', revenue: 20, rank_by_revenue: 2, gross_margin_pct: 0 },
      { product_id: 'a', product_name: 'A', revenue: 90, rank_by_revenue: 1 },
    ],
  });
  assert.deepEqual(rows.map((r) => r.id), ['a', 'b', 'c']);
  assert.equal(rows[1].grossMarginPct, 0);
  assert.equal(rows[0].cost, null);
  assert.equal(rows[2].cost, null);
});

test('hasProductSeries', () => {
  assert.equal(hasProductSeries({ products: [] }), false);
  assert.equal(hasProductSeries({ products: [{ product_id: 'x' }] }), true);
  assert.equal(hasProductSeries(null), false);
});

test('monthOverMonth never invents a change across a null month', () => {
  const rows = financialChartRows({
    financial_monthly: [
      { period: '2026-01', revenue: 100 },
      { period: '2026-02', revenue: null },
      { period: '2026-03', revenue: 150 },
    ],
  });
  const m = monthOverMonth(rows, 'revenue');
  assert.equal(m[0].change, null);
  assert.equal(m[1].change, null);
  assert.equal(m[2].change, null);
  assert.equal(m[2].percent, null);
});

test('monthOverMonth computes change and percent, and skips percent on a zero base', () => {
  const rows = financialChartRows({
    financial_monthly: [
      { period: '2026-01', revenue: 0 },
      { period: '2026-02', revenue: 50 },
      { period: '2026-03', revenue: 75 },
    ],
  });
  const m = monthOverMonth(rows, 'revenue');
  assert.equal(m[1].change, 50);
  assert.equal(m[1].percent, null);
  assert.equal(m[2].change, 25);
  assert.equal(m[2].percent, 50);
});
