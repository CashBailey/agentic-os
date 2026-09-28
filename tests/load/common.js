// Shared k6 configuration and helpers for the AgenticOS load suite.
//
// Environment variables:
//   BASE_URL      - Backend base URL (default http://localhost:8000)
//   PROJECT_SLUG  - Project slug used by memory/approvals tests (default 'default')

export const BASE_URL = (__ENV.BASE_URL || 'http://localhost:8000').replace(/\/+$/, '');
export const PROJECT_SLUG = __ENV.PROJECT_SLUG || 'default';

export const JSON_HEADERS = {
  'Content-Type': 'application/json',
  'Accept': 'application/json',
};

// Staged ramp used by audit / memory_search / approvals scripts.
// 0 -> 10 (30s), sustain 10 (1m), -> 100 (30s), sustain 100 (1m),
// -> 500 (30s), sustain 500 (1m).  ~5 minutes total.
export const STAGED_RAMP = [
  { duration: '30s', target: 10 },
  { duration: '1m',  target: 10 },
  { duration: '30s', target: 100 },
  { duration: '1m',  target: 100 },
  { duration: '30s', target: 500 },
  { duration: '1m',  target: 500 },
  { duration: '15s', target: 0 },
];

const QUERY_WORDS = [
  'authentication', 'pipeline', 'embedding', 'workflow', 'session',
  'approval', 'memory', 'router', 'agent', 'context', 'token', 'graph',
  'planner', 'rollback', 'cache', 'vector', 'prompt', 'persona',
];

export function randomQuery() {
  const n = 2 + Math.floor(Math.random() * 3);
  const out = [];
  for (let i = 0; i < n; i++) {
    out.push(QUERY_WORDS[Math.floor(Math.random() * QUERY_WORDS.length)]);
  }
  return out.join(' ');
}

export function url(path) {
  if (!path.startsWith('/')) path = '/' + path;
  return BASE_URL + path;
}
