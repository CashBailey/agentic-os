// Load test: mixed read/write against /approvals
// 70% GET (read budget p95<300ms), 30% POST (write budget p95<1000ms)
import http from 'k6/http';
import { check, sleep } from 'k6';
import { JSON_HEADERS, PROJECT_SLUG, STAGED_RAMP, url } from './common.js';

export const options = {
  stages: STAGED_RAMP,
  thresholds: {
    'http_req_duration{type:read}':  ['p(95)<300'],
    'http_req_duration{type:write}': ['p(95)<1000'],
    'http_req_failed': ['rate<0.02'],
  },
  discardResponseBodies: true,
};

function doRead() {
  const res = http.get(url('/approvals?limit=50'), {
    headers: JSON_HEADERS,
    tags: { type: 'read', endpoint: 'approvals_list' },
  });
  check(res, { 'approvals GET 2xx': (r) => r.status >= 200 && r.status < 300 });
}

function doWrite() {
  // ApprovalCreate requires: project_slug|project_id, tool, action, raw_input.
  // We include the originally-requested title/kind/payload fields too for
  // compatibility with any spec variant that consumes them.
  const body = JSON.stringify({
    project_slug: PROJECT_SLUG,
    tool: 'load_test',
    action: 'noop',
    raw_input: { source: 'k6', ts: Date.now() },
    title: 'load test',
    kind: 'tool_call',
    payload: {},
    risk: 'low',
    ttl_seconds: 60,
  });
  const res = http.post(url('/approvals'), body, {
    headers: JSON_HEADERS,
    tags: { type: 'write', endpoint: 'approvals_create' },
  });
  // Accept 2xx; some envs may 409/422 under load — treat as soft failure via
  // the http_req_failed threshold rather than a hard check.
  check(res, { 'approvals POST 2xx': (r) => r.status >= 200 && r.status < 300 });
}

export default function () {
  if (Math.random() < 0.7) {
    doRead();
  } else {
    doWrite();
  }
  sleep(1);
}
