// Load test: POST /projects/{slug}/memory/search/semantic (embedding budget p95 < 800ms)
import http from 'k6/http';
import { check, sleep } from 'k6';
import { JSON_HEADERS, PROJECT_SLUG, STAGED_RAMP, randomQuery, url } from './common.js';

export const options = {
  stages: STAGED_RAMP,
  thresholds: {
    'http_req_duration{type:embedding}': ['p(95)<800'],
    'http_req_failed': ['rate<0.01'],
  },
  discardResponseBodies: true,
};

const PATH = `/projects/${PROJECT_SLUG}/memory/search/semantic`;

export default function () {
  // Backend schema (SemanticSearchIn) uses `top_k`; include `limit` too for
  // forward-compat with clients that send the spec-style key.
  const body = JSON.stringify({ query: randomQuery(), top_k: 10, limit: 10 });
  const res = http.post(url(PATH), body, {
    headers: JSON_HEADERS,
    tags: { type: 'embedding', endpoint: 'memory_search' },
  });
  check(res, { 'memory search status 2xx': (r) => r.status >= 200 && r.status < 300 });
  sleep(1);
}
