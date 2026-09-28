import axios from 'axios';

// Base URL for the Agentic OS control-plane API.
// Defaults to the contract-spec port 8000; can be overridden via VITE_API_BASE_URL
// in `.env.local` (Round 2 dev uses 8765 because another local service squats 8000).
export const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://127.0.0.1:8000';

export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 8_000,
  headers: { 'Content-Type': 'application/json' },
});

export type ReadinessStatus = 'ok' | 'degraded' | 'down';

export async function fetchReadiness(): Promise<ReadinessStatus> {
  try {
    const res = await api.get('/healthz', { timeout: 2_000 });
    if (res.status >= 200 && res.status < 300) return 'ok';
    return 'degraded';
  } catch {
    return 'down';
  }
}

// ---------------- Types (derived from OpenAPI probe) ----------------

export interface Project {
  id: number;
  slug: string;
  name: string;
  root_path: string;
  created_at: string;
  updated_at: string;
}

export type CliKind = 'claude' | 'gemini' | 'codex';

export interface AuthStatusEntry {
  cli: CliKind | string;
  state: string;
  recommended_command: string;
  warnings: string[];
}
export interface AuthStatusResponse {
  clis: AuthStatusEntry[];
}

export interface ContextDocument {
  id: number;
  project_id: number | null;
  scope: string;
  kind: string;
  path: string;
  content: string;
  hash?: string;
  created_at: string;
  updated_at: string;
}

export interface MemoryItem {
  id: number;
  project_id: number;
  kind: string;
  title: string;
  body: string;
  tags: string[];
  occurred_at: string;
  created_at: string;
  updated_at: string;
}

export interface SemanticHit {
  id: number;
  score: number;
  title: string;
  body: string;
  kind: string;
}

export interface SessionSummary {
  id: number;
  project_id: number;
  started_at: string;
  ended_at: string | null;
  summary: string;
  tokens_in?: number;
  tokens_out?: number;
}

export interface AdapterGeneration {
  id: number;
  project_id: number;
  cli: CliKind | string;
  output_path: string;
  hash: string;
  status: string;
  created_at: string;
}

export interface AdapterDiff {
  cli: string;
  target: string;
  diff: string;
  identical: boolean;
}

export interface PolicyFile {
  kind: string;
  path: string;
  content: string;
  parse_ok?: boolean;
  parse_error?: string | null;
}

export interface PolicySimulationResult {
  decision: string;
  matched_rule: string | null;
  reason?: string;
}

export interface Skill {
  name: string;
  path: string;
  description?: string;
  when_to_use?: string[];
  inputs?: unknown;
  outputs?: unknown;
  safety?: string[];
  body?: string;
}

export interface Workflow {
  name: string;
  path: string;
  description?: string;
  steps?: string[];
  applies_to?: string[];
  body?: string;
}

export interface Approval {
  id: number;
  project_id: number | null;
  tool: string;
  action: string;
  raw_input: Record<string, unknown>;
  risk: string;
  status: string;
  expires_at: string | null;
  created_at: string;
}

export interface AuditEvent {
  id: number;
  ts?: string;
  created_at?: string;
  event_type: string;
  actor: string | null;
  project_id: number | null;
  payload: Record<string, unknown>;
}

export interface AuditPage {
  items: AuditEvent[];
  next_cursor: string | null;
}

// ---------------- Thin wrappers ----------------

const j = <T,>(p: Promise<{ data: T }>): Promise<T> => p.then((r) => r.data);

export const ProjectsAPI = {
  list: () => j<Project[]>(api.get('/projects')),
  detail: (slug: string) => j<Project>(api.get(`/projects/${slug}`)),
  create: (body: { slug: string; name: string; root_path: string }) =>
    j<Project>(api.post('/projects', body)),
};

export const AuthAPI = {
  status: () => j<AuthStatusResponse>(api.get('/auth-status')),
};

export const ContextAPI = {
  list: (slug: string) => j<ContextDocument[]>(api.get(`/projects/${slug}/context`)),
  update: (slug: string, docId: number, content: string) =>
    j<ContextDocument>(api.put(`/projects/${slug}/context/${docId}`, { content })),
};

export const MemoryAPI = {
  list: (slug: string, params: { q?: string; kind?: string; limit?: number } = {}) =>
    j<MemoryItem[]>(api.get(`/projects/${slug}/memory`, { params })),
  create: (
    slug: string,
    body: { kind: string; title: string; body: string; tags?: string[] },
  ) => j<MemoryItem>(api.post(`/projects/${slug}/memory`, body)),
  semantic: (slug: string, body: { query: string; top_k?: number }) =>
    j<SemanticHit[]>(api.post(`/projects/${slug}/memory/search/semantic`, body)),
};

export const SessionsAPI = {
  list: (slug: string, limit = 50) =>
    j<SessionSummary[]>(api.get(`/projects/${slug}/sessions`, { params: { limit } })),
};

export const AdaptersAPI = {
  list: (slug: string) => j<AdapterGeneration[]>(api.get(`/projects/${slug}/adapters`)),
  compile: (slug: string) =>
    j<{ task_id: number }>(api.post(`/projects/${slug}/adapters/compile`)),
  diff: (slug: string, cli: string, target: string) =>
    j<AdapterDiff>(api.get(`/projects/${slug}/adapters/${cli}/diff`, { params: { target } })),
};

export const PoliciesAPI = {
  list: (slug: string) => j<PolicyFile[]>(api.get(`/projects/${slug}/policies`)),
  update: (slug: string, kind: string, content: string) =>
    j<PolicyFile>(api.put(`/projects/${slug}/policies/${kind}`, { content })),
  simulate: (
    slug: string,
    body: { tool: string; action: string; args: Record<string, unknown> },
  ) => j<PolicySimulationResult>(api.post(`/projects/${slug}/policies/simulate`, body)),
};

export const SkillsAPI = { list: () => j<Skill[]>(api.get('/skills')) };
export const WorkflowsAPI = { list: () => j<Workflow[]>(api.get('/workflows')) };

export const ApprovalsAPI = {
  list: (status?: string) =>
    j<Approval[]>(api.get('/approvals', { params: status ? { status } : {} })),
  decide: (id: number, body: { decision: 'approved' | 'denied'; reason?: string }) =>
    j<Approval>(api.post(`/approvals/${id}/decide`, body)),
};

export const AuditAPI = {
  page: (params: { cursor?: string; project?: string; since?: string } = {}) =>
    j<AuditPage>(api.get('/audit', { params })),
};

// Human-readable error extractor for query/mutation error cards.
export function describeError(e: unknown): string {
  if (!e) return 'Unknown error';
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const any = e as any;
  if (any?.message === 'Network Error' || any?.code === 'ERR_NETWORK')
    return 'Backend offline (network error).';
  if (any?.response?.status) {
    const d = any.response.data?.detail ?? any.response.statusText;
    return `${any.response.status} ${typeof d === 'string' ? d : JSON.stringify(d)}`;
  }
  if (any?.message) return String(any.message);
  return String(e);
}

export function isNetworkError(e: unknown): boolean {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const any = e as any;
  return any?.message === 'Network Error' || any?.code === 'ERR_NETWORK';
}
