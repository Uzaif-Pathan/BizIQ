import { describe, it, expect } from 'vitest';
import {
  MAX_IMPORT_BYTES,
  IMPORT_TYPES,
  checkImportFile,
  templateCsv,
  importStatusInfo,
  isUsableImport,
  hasUsableImport,
  describeImportResult,
  importsSummary,
  importTypeLabel,
} from '../src/utils/imports';

const file = (name, size = 100) => ({ name, size });

describe('checkImportFile', () => {
  it('accepts a normal csv', () => {
    expect(checkImportFile(file('financials.csv'))).toBeNull();
    expect(checkImportFile(file('DATA.CSV'))).toBeNull();
  });
  it('asks for a file when none is chosen', () => {
    expect(checkImportFile(null)).toMatch(/Choose a CSV/);
  });
  it('rejects Excel and other types because the backend accepts only .csv', () => {
    for (const n of ['a.xlsx', 'a.xls', 'a.txt', 'a.csv.exe', 'csv']) {
      expect(checkImportFile(file(n))).toMatch(/Unsupported file type/);
    }
  });
  it('rejects empty files and files over 5 MB (the backend limit)', () => {
    expect(checkImportFile(file('a.csv', 0))).toMatch(/empty/);
    expect(checkImportFile(file('a.csv', MAX_IMPORT_BYTES))).toBeNull();
    expect(checkImportFile(file('a.csv', MAX_IMPORT_BYTES + 1))).toMatch(/larger than 5 MB/);
  });
});

describe('import types', () => {
  it('uses exactly the three backend data types', () => {
    expect(IMPORT_TYPES.map((t) => t.value)).toEqual(['financials', 'customers', 'products']);
    expect(importTypeLabel('customers')).toBe('Customer data');
    expect(importTypeLabel('other')).toBe('other');
  });
  it('builds a template whose header matches the backend columns', () => {
    expect(templateCsv('financials').split('\n')[0]).toBe('period,revenue,expenses,expenses_complete');
    expect(templateCsv('customers').split('\n')[0]).toBe('period,customer_id,transactions,amount_spent');
    expect(templateCsv('products').split('\n')[0]).toBe('period,product_id,product_name,units_sold,revenue,cost');
    for (const t of IMPORT_TYPES) {
      const [header, row] = templateCsv(t.value).trim().split('\n');
      expect(row.split(',').length).toBe(header.split(',').length);
    }
  });
});

describe('statuses', () => {
  it('maps every backend status to a label and tone', () => {
    expect(importStatusInfo('completed')).toEqual({ label: 'Validated', tone: 'green' });
    expect(importStatusInfo('completed_with_warnings').tone).toBe('amber');
    expect(importStatusInfo('failed').label).toBe('Failed validation');
    expect(importStatusInfo('weird').label).toBe('weird');
  });
  it('treats only completed imports as usable data', () => {
    expect(isUsableImport({ status: 'completed' })).toBe(true);
    expect(isUsableImport({ status: 'completed_with_warnings' })).toBe(true);
    expect(isUsableImport({ status: 'failed' })).toBe(false);
    expect(hasUsableImport([{ status: 'failed' }])).toBe(false);
    expect(hasUsableImport([{ status: 'failed' }, { status: 'completed' }])).toBe(true);
    expect(hasUsableImport([])).toBe(false);
    expect(hasUsableImport(undefined)).toBe(false);
  });
});

describe('describeImportResult', () => {
  it('reports a clean import', () => {
    const r = describeImportResult({ file_name: 'f.csv', status: 'completed', row_count: 24, valid_row_count: 24 });
    expect(r.tone).toBe('success');
    expect(r.text).toContain('24 of 24 rows were accepted');
  });
  it('reports warnings as saved but to be reviewed', () => {
    const r = describeImportResult({ file_name: 'f.csv', status: 'completed_with_warnings', row_count: 10, valid_row_count: 9 });
    expect(r.tone).toBe('success');
    expect(r.text).toMatch(/with warnings/);
  });
  it('reports a failed import as not saved', () => {
    const r = describeImportResult({ file_name: 'f.csv', status: 'failed', row_count: 5, valid_row_count: 0 });
    expect(r.tone).toBe('warn');
    expect(r.text).toMatch(/nothing was saved/);
  });
  it('does not invent row counts that are missing', () => {
    expect(describeImportResult({ file_name: 'f.csv', status: 'completed' }).text).not.toMatch(/rows were accepted/);
  });
});

describe('importsSummary', () => {
  const item = (data_type, status) => ({ data_type, status });
  it('says so when nothing was uploaded', () => {
    expect(importsSummary([]).value).toBe('No files');
    expect(importsSummary(undefined).tone).toBe('neutral');
  });
  it('is validated when every data type is valid', () => {
    const s = importsSummary([item('financials', 'completed'), item('customers', 'completed')]);
    expect(s).toMatchObject({ value: 'Validated', tone: 'green' });
  });
  it('flags a data type whose newest upload failed', () => {
    const s = importsSummary([item('financials', 'failed'), item('customers', 'completed')]);
    expect(s).toMatchObject({ value: 'Needs attention', tone: 'amber' });
  });
  it('ignores an old failed upload that was replaced by a newer valid one (list is newest first)', () => {
    const s = importsSummary([item('financials', 'completed'), item('financials', 'failed')]);
    expect(s.value).toBe('Validated');
  });
  it('shows warnings without calling them failures', () => {
    expect(importsSummary([item('financials', 'completed_with_warnings')]).value).toBe('Valid, with warnings');
  });
});
