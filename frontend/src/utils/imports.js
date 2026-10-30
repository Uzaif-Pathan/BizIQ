// Pure helpers for uploading business data (CSV files) to the backend import API.
// The rules here mirror backend/app/services/import_service.py and backend/app/api/v1/endpoints/imports.py.

export const MAX_IMPORT_BYTES = 5 * 1024 * 1024; // the backend rejects larger files with 413

// The three kinds of file the backend accepts. `value` is the backend's data_type.
export const IMPORT_TYPES = [
  {
    value: 'financials',
    label: 'Financial records',
    columns: ['period', 'revenue', 'expenses', 'expenses_complete'],
    hint: 'One row per month: revenue, expenses, and whether the expense list is complete.',
  },
  {
    value: 'customers',
    label: 'Customer data',
    columns: ['period', 'customer_id', 'transactions', 'amount_spent'],
    hint: 'One row per customer per month.',
  },
  {
    value: 'products',
    label: 'Product / service data',
    columns: ['period', 'product_id', 'product_name', 'units_sold', 'revenue', 'cost'],
    hint: 'One row per product or service per month.',
  },
];

export const importTypeLabel = (value) => IMPORT_TYPES.find((t) => t.value === value)?.label ?? value;

// Returns an error message, or null when the file can be sent. Only .csv is accepted by the backend.
export function checkImportFile(file) {
  if (!file) return 'Choose a CSV file first.';
  if (!/\.csv$/i.test(file.name || '')) return 'Unsupported file type. Choose a .csv file (save Excel sheets as CSV UTF-8).';
  if (file.size === 0) return 'The file is empty.';
  if (file.size > MAX_IMPORT_BYTES) return 'File is larger than 5 MB. Choose a smaller file.';
  return null;
}

// Header row plus one example row, using the exact columns the backend expects.
export function templateCsv(dataType) {
  const examples = {
    financials: ['2025-01', '100000', '80000', 'true'],
    customers: ['2025-01', 'C001', '4', '2500'],
    products: ['2025-01', 'P001', 'Example item', '20', '10000', '6000'],
  };
  const type = IMPORT_TYPES.find((t) => t.value === dataType) ?? IMPORT_TYPES[0];
  return `${type.columns.join(',')}\n${examples[type.value].join(',')}\n`;
}

const STATUS = {
  pending: { label: 'Waiting', tone: 'neutral' },
  processing: { label: 'Checking…', tone: 'neutral' },
  completed: { label: 'Validated', tone: 'green' },
  completed_with_warnings: { label: 'Validated with warnings', tone: 'amber' },
  failed: { label: 'Failed validation', tone: 'amber' },
};

export function importStatusInfo(status) {
  return STATUS[status] ?? { label: String(status ?? 'Unknown'), tone: 'neutral' };
}

// An import whose rows were stored and can be analysed.
export const isUsableImport = (item) =>
  item?.status === 'completed' || item?.status === 'completed_with_warnings';

export const hasUsableImport = (imports) => (imports || []).some(isUsableImport);

// What the upload form tells the user right after a file was sent.
export function describeImportResult(item) {
  const name = item?.file_name ?? 'The file';
  const accepted = item?.valid_row_count;
  const received = item?.row_count;
  const rows = accepted != null && received != null ? ` ${accepted} of ${received} rows were accepted.` : '';
  if (item?.status === 'failed') {
    return { tone: 'warn', text: `“${name}” failed validation and nothing was saved.${rows} See the issues below.` };
  }
  if (item?.status === 'completed_with_warnings') {
    return { tone: 'success', text: `“${name}” was validated and saved with warnings.${rows} Review the issues below.` };
  }
  return { tone: 'success', text: `“${name}” was validated and saved.${rows}` };
}

// One-line summary of all imports of a business, for status cards.
export function importsSummary(imports) {
  const list = imports || [];
  if (!list.length) return { value: 'No files', detail: 'Nothing uploaded yet', tone: 'neutral' };
  // Only the newest import of each data type counts: an older failed upload that was later replaced is no problem.
  const latest = new Map();
  for (const i of list) if (!latest.has(i.data_type)) latest.set(i.data_type, i);
  const items = [...latest.values()];
  const failed = items.filter((i) => i.status === 'failed').length;
  const warned = items.filter((i) => i.status === 'completed_with_warnings').length;
  const ok = items.filter(isUsableImport).length;
  if (failed) return { value: 'Needs attention', detail: `${failed} of ${items.length} data types failed validation`, tone: 'amber' };
  if (warned) return { value: 'Valid, with warnings', detail: `${ok} of ${items.length} data types validated`, tone: 'amber' };
  if (ok === items.length) return { value: 'Validated', detail: `${ok} of ${items.length} data types validated`, tone: 'green' };
  return { value: 'Checking…', detail: 'Validation in progress', tone: 'neutral' };
}
