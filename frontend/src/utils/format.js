// Number formatters used across the app. Missing values are shown as a dash, never as zero.
const isMissing = (n) => n === null || n === undefined || Number.isNaN(Number(n));

export const currency = (n) =>
  isMissing(n)
    ? '—'
    : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 0 }).format(Number(n));

export const pct = (n) => (isMissing(n) ? '—' : `${Number(n).toFixed(1)}%`);
