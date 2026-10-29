import { describe, it, expect, afterEach, vi } from 'vitest';
// Node 18 has no global File (browsers and Node 20+ do), so take it from node:buffer.
import { File } from 'node:buffer';
import {
  api,
  ApiError,
  describeError,
  businessToApi,
  businessCreateFromLocal,
  businessUpdateFromProfile,
  businessFromApi,
} from '../src/services/api';

const jsonResponse = (status: number, body: unknown) => ({ ok: status < 400, status, json: async () => body });

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('request errors', () => {
  it('reports an unreachable server', async () => {
    vi.stubGlobal('fetch', async () => {
      throw new TypeError('fetch failed');
    });
    const err: any = await api.listBusinesses().catch((e) => e);
    expect(err instanceof ApiError).toBe(true);
    expect(err.status).toBe(0);
    expect(err.code).toBe('network_error');
    expect(describeError(err)).toBe('Cannot reach the BizIQ server. Check that the backend is running.');
  });

  it('turns a validation error into a readable message', async () => {
    vi.stubGlobal('fetch', async () =>
      jsonResponse(422, {
        error: {
          code: 'validation_error',
          message: 'Request validation failed.',
          details: [{ field: 'name', message: 'String should have at least 2 characters' }],
        },
      }),
    );
    const err: any = await api.createBusiness({ name: 'A', industry: 'Retail', business_type: 'retail' }).catch((e) => e);
    expect(err.status).toBe(422);
    expect(err.code).toBe('validation_error');
    expect(describeError(err)).toBe('Request validation failed. name: String should have at least 2 characters');
  });

  it('keeps the status of a 404 so callers can react to it', async () => {
    vi.stubGlobal('fetch', async () =>
      jsonResponse(404, { error: { code: 'not_found', message: 'Business not found.', details: null } }),
    );
    const err: any = await api.getBusiness('missing').catch((e) => e);
    expect(err instanceof ApiError).toBe(true);
    expect(err.status).toBe(404);
    expect(err.message).toBe('Business not found.');
  });

  it('copes with an error body that is not JSON', async () => {
    vi.stubGlobal('fetch', async () => ({
      ok: false,
      status: 500,
      json: async () => {
        throw new Error('not json');
      },
    }));
    const err: any = await api.health().catch((e) => e);
    expect(err.status).toBe(500);
    expect(err.code).toBe('http_error');
    expect(err.message).toBe('Request failed (500).');
  });

  it('gives a generic message for errors that are not ApiErrors', () => {
    expect(describeError(new Error('boom'))).toBe('Something went wrong. Please try again.');
  });
});

describe('requests', () => {
  it('runs an analysis with POST on the business analyses route', async () => {
    let seen: any;
    vi.stubGlobal('fetch', async (url: string, options: any) => {
      seen = { url, method: options.method };
      return jsonResponse(201, {});
    });
    await api.runAnalysis('abc-123');
    expect(seen.url.endsWith('/businesses/abc-123/analyses')).toBe(true);
    expect(seen.method).toBe('POST');
  });

  it('updates a business with PATCH and a JSON body', async () => {
    let seen: any;
    vi.stubGlobal('fetch', async (url: string, options: any) => {
      seen = { url, method: options.method, body: options.body };
      return jsonResponse(200, {});
    });
    await api.updateBusiness('abc-123', { name: 'New name' });
    expect(seen.url.endsWith('/businesses/abc-123')).toBe(true);
    expect(seen.method).toBe('PATCH');
    expect(seen.body).toBe('{"name":"New name"}');
  });
});

describe('business mapping', () => {
  it('splits "City, State", lowercases the type and trims the name', () => {
    expect(
      businessToApi({ name: ' Shop ', industry: 'Retail', type: 'Service', location: 'Nashik, Maharashtra' }),
    ).toEqual({ name: 'Shop', industry: 'Retail', business_type: 'service', city: 'Nashik', state: 'Maharashtra' });
  });

  it('sends null for a missing state', () => {
    const payload = businessToApi({ name: 'Shop', industry: 'Retail', type: 'Retail', location: 'Nashik' });
    expect(payload.city).toBe('Nashik');
    expect(payload.state).toBe(null);
  });

  it('carries the profile description and stage over when saving a local business', () => {
    const base = { name: 'Old Shop', industry: 'Retail', type: 'Retail', location: 'A, B' };
    const launching = businessCreateFromLocal(base, { description: ' Hello ', stage: 'Launching' });
    expect(launching.description).toBe('Hello');
    expect(launching.stage).toBe('new');
    const expanding = businessCreateFromLocal(base, { description: '  ', stage: 'Expanding' });
    expect(expanding.description).toBe(null);
    expect(expanding.stage).toBe('established');
    expect(businessCreateFromLocal(base).stage).toBe(undefined);
  });

  it('maps profile stages Idea and Launching to new, others to established', () => {
    const form = { name: 'X', industry: 'I', type: 'Retail', location: 'P, Q', description: '' };
    expect(businessUpdateFromProfile({ ...form, stage: 'Idea' }).stage).toBe('new');
    expect(businessUpdateFromProfile({ ...form, stage: 'Operating' }).stage).toBe('established');
  });

  it('turns a server business into the shape the screens use', () => {
    const server: any = {
      id: 'u1', name: 'N', industry: 'I', business_type: 'retail', stage: 'established',
      city: 'Nashik', state: null, country: 'India', goals: [], created_at: '', updated_at: '',
      latest_analysis_status: null,
    };
    expect(businessFromApi(server, { hasData: true, updated: '05 Oct 2026' })).toEqual({
      id: 'u1', name: 'N', industry: 'I', type: 'Retail', location: 'Nashik',
      hasData: true, updated: '05 Oct 2026', level: 'Limited / Cold Start',
      analysisStatus: null, synced: true,
    });
  });
});

describe('benchmarks', () => {
  it('fetches the industry comparison for a business from its own endpoint', async () => {
    let url = '';
    vi.stubGlobal('fetch', async (u: string) => {
      url = u;
      return jsonResponse(200, {
        business_id: '7', status: 'available', levels_tried: ['district', 'state', 'region', 'national'],
        notes: [], matched_state: 'Maharashtra',
        items: [{
          metric: 'gva_per_worker', label: 'Value added per worker', definition: 'd', value: 100,
          geography_level_used: 'state', geography: 'Maharashtra', industry_used: 'Trade', year: 2025,
          source: 'ASUSE 2025', specificity: 'broad_sector',
        }],
      });
    });
    const out = await api.getBenchmarks('7');
    expect(url.endsWith('/businesses/7/benchmarks')).toBe(true);
    expect(out.items[0].specificity).toBe('broad_sector');
  });
});

describe('data imports', () => {
  const importRecord = {
    id: '3', business_id: '7', data_type: 'financials', file_name: 'financials.csv', status: 'completed',
    row_count: 24, valid_row_count: 24, error_count: 0, warning_count: 0,
    created_at: '2026-10-30T00:00:00Z', updated_at: '2026-10-30T00:00:00Z',
  };

  it('uploads a CSV as multipart form data and does not force a JSON content type', async () => {
    let url = '';
    let init: any = null;
    vi.stubGlobal('fetch', async (u: string, i: any) => {
      url = u;
      init = i;
      return jsonResponse(201, importRecord);
    });
    const file = new File(['period,revenue\n2025-01,100\n'], 'financials.csv', { type: 'text/csv' });
    const out = await api.uploadImport('7', 'financials', file);
    expect(url.endsWith('/businesses/7/imports')).toBe(true);
    expect(init.method).toBe('POST');
    expect(init.body instanceof FormData).toBe(true);
    expect(init.body.get('data_type')).toBe('financials');
    expect((init.body.get('file') as File).name).toBe('financials.csv');
    // The browser must add the multipart boundary itself, so no Content-Type may be set here.
    expect(Object.keys(init.headers).map((h) => h.toLowerCase())).not.toContain('content-type');
    expect(out.status).toBe('completed');
  });

  it('still sends JSON requests with a JSON content type', async () => {
    let init: any = null;
    vi.stubGlobal('fetch', async (_u: string, i: any) => {
      init = i;
      return jsonResponse(200, []);
    });
    await api.listBusinesses();
    expect(init.headers['Content-Type']).toBe('application/json');
  });

  it('shows the backend reason when a file is rejected', async () => {
    vi.stubGlobal('fetch', async () =>
      jsonResponse(400, { error: { code: 'bad_request', message: 'The file is not UTF-8 text. Please save it as a CSV (UTF-8).' } }),
    );
    const file = new File(['x'], 'a.csv');
    const err: any = await api.uploadImport('7', 'customers', file).catch((e) => e);
    expect(err instanceof ApiError).toBe(true);
    expect(err.status).toBe(400);
    expect(describeError(err)).toContain('not UTF-8');
  });

  it('lists imports and their issues from the right routes', async () => {
    const urls: string[] = [];
    vi.stubGlobal('fetch', async (u: string) => {
      urls.push(u);
      return jsonResponse(200, []);
    });
    await api.listImports('7');
    await api.getImport('7', '3');
    await api.listImportIssues('7', '3', { severity: 'error', limit: 20, offset: 40 });
    expect(urls[0].endsWith('/businesses/7/imports')).toBe(true);
    expect(urls[1].endsWith('/businesses/7/imports/3')).toBe(true);
    expect(urls[2].endsWith('/businesses/7/imports/3/issues?severity=error&limit=20&offset=40')).toBe(true);
  });
});
