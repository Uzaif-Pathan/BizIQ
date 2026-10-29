const BASE_URL: string =
  (import.meta as any).env?.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000/api/v1';

// ---------- Errors ----------
export class ApiError extends Error {
  status: number;
  code: string;
  details: any;
  constructor(status: number, code: string, message: string, details?: any) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function describeError(err: unknown): string {
  if (err instanceof ApiError) {
    const first = Array.isArray(err.details) ? err.details[0] : null;
    return first
      ? `${err.message} ${first.field ? first.field + ': ' : ''}${first.message}`
      : err.message;
  }
  return 'Something went wrong. Please try again.';
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    });
  } catch {
    throw new ApiError(0, 'network_error', 'Cannot reach the BizIQ server. Check that the backend is running.');
  }
  if (res.status === 204) return undefined as T;
  if (!res.ok) {
    let body: any = null;
    try { body = await res.json(); } catch { /* error body was not JSON */ }
    const err = body?.error;
    throw new ApiError(
      res.status,
      err?.code ?? 'http_error',
      err?.message ?? `Request failed (${res.status}).`,
      err?.details,
    );
  }
  return (await res.json()) as T;
}

// ---------- Types (from contracts/analysis-result.schema.json and business.py) ----------
export type AnalysisStatus = 'pending' | 'completed' | 'failed';
export type EvidenceLevel = 'insufficient' | 'low' | 'medium' | 'high';
export type BenchmarkStatus = 'available' | 'partial' | 'unavailable';
export type Severity = 'info' | 'warning' | 'critical';
export type Priority = 'high' | 'medium' | 'low';
export type BusinessType = 'retail' | 'service' | 'manufacturing' | 'hybrid' | 'other';

export interface Metrics {
  revenue: number | null;
  expenses: number | null;
  profit: number | null;
  profit_margin: number | null; // percent
  [extra: string]: number | null | undefined;
}
export interface Finding {
  finding_id: string;
  category: 'financial' | 'customer' | 'product' | 'trend' | 'benchmark' | 'data_quality';
  title: string;
  description: string;
  metric_name?: string | null;
  metric_value?: number | null;
  severity: Severity;
  evidence: string[];
}
export interface Recommendation {
  recommendation_id: string;
  title: string;
  issue: string;
  reason: string;
  action: string;
  priority: Priority;
  supporting_finding_ids: string[];
  evidence: string[];
  kpi?: string | null;
  expected_direction?: 'increase' | 'decrease' | 'maintain' | null;
}
// ---- Optional fields added by the real analytics engine (all may be absent or null) ----
// Any numeric value inside `series` can be null. Treat null as "unknown", never as 0
// (see src/utils/series.js).
export interface FinancialMonth {
  period: string; // 'YYYY-MM'
  revenue: number | null;
  expenses: number | null;
  expenses_complete: boolean | null;
  profit: number | null;
  needs_review: boolean | null;
  listed_expenses_exceed_revenue: boolean | null;
}
export interface CustomerMonth {
  period: string;
  active_customers: number | null;
  spend: number | null;
  transactions: number | null;
}
export interface ProductSeriesRow {
  product_id: string;
  product_name: string;
  months_active: number | null;
  revenue: number | null;
  units_sold: number | null;
  cost: number | null;
  gross_profit: number | null;
  gross_margin_pct: number | null;
  revenue_share_pct: number | null;
  rank_by_revenue: number | null;
}
export interface AnalysisSeries {
  financial_monthly?: FinancialMonth[] | null;
  customer_monthly?: CustomerMonth[] | null;
  products?: ProductSeriesRow[] | null;
}
// Shapes below are not confirmed by Person 2 yet, so they are kept loose on purpose.
export type LooseObject = Record<string, unknown>;

export interface AnalysisResult {
  analysis_id: string;
  business_id: string;
  status: AnalysisStatus;
  metrics: Metrics;
  findings: Finding[];
  recommendations: Recommendation[];
  evidence_level: EvidenceLevel;
  benchmark_status: BenchmarkStatus;
  method_version?: string | null;
  limitations: string[];
  error_message?: string | null;
  created_at?: string | null;
  completed_at?: string | null;
  series?: AnalysisSeries | null;
  metric_details?: LooseObject | null;
  health_score?: LooseObject | number | null;
  models?: LooseObject | null;
  validation?: LooseObject | null;
  data_coverage?: LooseObject | null;
  engine_status?: LooseObject | string | null;
}
export interface AnalysisRunSummary {
  analysis_id: string;
  business_id: string;
  status: AnalysisStatus;
  evidence_level?: EvidenceLevel | null;
  method_version?: string | null;
  created_at: string;
  completed_at?: string | null;
}
export interface BusinessCreate {
  name: string;
  industry: string;
  business_type: BusinessType;
  stage?: 'new' | 'established';
  city?: string | null;
  district?: string | null;
  state?: string | null;
  country?: string;
  employee_count?: number | null;
  description?: string | null;
  goals?: string[];
}
export type BusinessUpdate = Partial<BusinessCreate>;
export interface BusinessRead extends BusinessCreate {
  id: string;
  stage: 'new' | 'established';
  country: string;
  goals: string[];
  latest_analysis_status?: AnalysisStatus | null;
  created_at: string;
  updated_at: string;
}
export interface ReportPayload {
  business: BusinessRead;
  analysis: AnalysisResult;
  generated_at: string;
}

// Industry comparison from the ASUSE survey. Context only: value added and pay, NOT profit margin,
// and never part of the analysis result or the health score.
export type BenchmarkSpecificity = 'all_industries' | 'broad_sector' | 'detailed_activity';
export interface BenchmarkItem {
  metric: string;
  label: string;
  definition: string;
  value: number;
  unit?: string | null;
  geography_level_used: string;
  geography: string;
  industry_used: string;
  sector?: string | null;
  establishment_type?: string | null;
  worker_group?: string | null;
  year: number;
  source: string;
  note?: string | null;
  specificity: BenchmarkSpecificity;
  specificity_note?: string | null;
}
export interface BenchmarkResponse {
  business_id: string;
  status: 'available' | 'partial' | 'unavailable';
  items: BenchmarkItem[];
  matched_industry?: { broad_sector: string; activity: string; match: 'keyword' | 'business_type' | 'none' } | null;
  matched_state?: string | null;
  levels_tried: string[];
  notes: string[];
}

// ---------- API calls ----------
export const api = {
  health: () => request<unknown>('/health'),

  listBusinesses: (limit = 50, offset = 0) =>
    request<BusinessRead[]>(`/businesses?limit=${limit}&offset=${offset}`),
  getBusiness: (id: string) => request<BusinessRead>(`/businesses/${id}`),
  createBusiness: (data: BusinessCreate) =>
    request<BusinessRead>('/businesses', { method: 'POST', body: JSON.stringify(data) }),
  updateBusiness: (id: string, data: BusinessUpdate) =>
    request<BusinessRead>(`/businesses/${id}`, { method: 'PATCH', body: JSON.stringify(data) }),
  deleteBusiness: (id: string) =>
    request<void>(`/businesses/${id}`, { method: 'DELETE' }),

  runAnalysis: (businessId: string) =>
    request<AnalysisResult>(`/businesses/${businessId}/analyses`, { method: 'POST' }),
  listAnalyses: (businessId: string) =>
    request<AnalysisRunSummary[]>(`/businesses/${businessId}/analyses`),
  getAnalysis: (id: string) => request<AnalysisResult>(`/analyses/${id}`),
  getFindings: (id: string) => request<Finding[]>(`/analyses/${id}/findings`),
  getRecommendations: (id: string) => request<Recommendation[]>(`/analyses/${id}/recommendations`),
  getReport: (id: string) => request<ReportPayload>(`/analyses/${id}/report`),

  getBenchmarks: (businessId: string) => request<BenchmarkResponse>(`/businesses/${businessId}/benchmarks`),
};

// ---------- Mapping between the backend and the existing UI shape ----------
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

// Backend business -> the shape App.jsx already uses.
// `local` carries the local-only fields (hasData, updated, level) of the same business.
export function businessFromApi(b: BusinessRead, local: any = {}) {
  return {
    id: b.id,
    name: b.name,
    industry: b.industry,
    type: cap(b.business_type),
    location: [b.city, b.state].filter(Boolean).join(', '),
    hasData: local.hasData ?? false,
    updated: local.updated ?? 'No analysis yet',
    level: local.level ?? 'Limited / Cold Start',
    analysisStatus: b.latest_analysis_status ?? null,
    synced: true,
  };
}

// Form values -> backend payload. ASSUMPTION (Person 3 has not confirmed):
// "City, State" is split on the first comma; any further parts are ignored.
export function businessToApi(f: { name: string; industry: string; type: string; location: string }): BusinessCreate {
  const [city, state] = f.location.split(',').map((s) => s.trim());
  return {
    name: f.name.trim(),
    industry: f.industry,
    business_type: f.type.toLowerCase() as BusinessType,
    city: city || null,
    state: state || null,
  };
}

// ASSUMPTION (not confirmed): stages "Idea"/"Launching" -> "new", every other stage -> "established".
const stageToApi = (stage: string): 'new' | 'established' =>
  ['Idea', 'Launching'].includes(stage) ? 'new' : 'established';

// A business that only exists on this device -> payload for creating it on the server.
// Carries over the description and stage from the local profile when there is one.
export function businessCreateFromLocal(
  b: { name: string; industry: string; type: string; location: string },
  profile?: { description?: string; stage?: string },
): BusinessCreate {
  const base = businessToApi(b);
  if (!profile) return base;
  return {
    ...base,
    description: (profile.description || '').trim() || null,
    stage: stageToApi(profile.stage || 'Operating'),
  };
}

// Profile form -> PATCH payload. Only fields the backend knows about are sent.
// ASSUMPTIONS (Person 3 has not confirmed): stages "Idea"/"Launching" -> "new",
// every other stage -> "established". Team size, website and currency stay on this device only.
export function businessUpdateFromProfile(f: {
  name: string; industry: string; type: string; location: string; description: string; stage: string;
}): BusinessUpdate {
  const [city, state] = f.location.split(',').map((s) => s.trim());
  return {
    name: f.name.trim(),
    industry: f.industry,
    business_type: f.type.toLowerCase() as BusinessType,
    city: city || null,
    state: state || null,
    description: f.description.trim() || null,
    stage: stageToApi(f.stage),
  };
}
