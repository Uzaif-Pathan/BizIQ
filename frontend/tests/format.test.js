import { describe, it, expect } from 'vitest';
import { currency, pct } from '../src/utils/format';

describe('currency', () => {
  it('shows a dash for missing values, never zero', () => {
    expect(currency(null)).toBe('—');
    expect(currency(undefined)).toBe('—');
    expect(currency(NaN)).toBe('—');
    expect(currency('abc')).toBe('—');
  });

  it('shows a real zero as zero', () => {
    expect(currency(0)).toBe('₹0');
  });

  it('formats rupees with Indian digit grouping', () => {
    expect(currency(286800)).toBe('₹2,86,800');
    expect(currency(66800)).toBe('₹66,800');
  });
});

describe('pct', () => {
  it('shows a dash for missing values, never 0%', () => {
    expect(pct(null)).toBe('—');
    expect(pct(undefined)).toBe('—');
  });

  it('formats one decimal place', () => {
    expect(pct(23.2915)).toBe('23.3%');
    expect(pct(0)).toBe('0.0%');
  });
});
