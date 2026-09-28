// Load test: GET /audit (read budget p95 < 300ms)
import http from 'k6/http';
import { check, sleep } from 'k6';
import { JSON_HEADERS, STAGED_RAMP, url } from './common.js';

export const options = {
  stages: STAGED_RAMP,
  thresholds: {
    'http_req_duration{type:read}': ['p(95)<300'],
    'http_req_failed': ['rate<0.01'],
  },
  discardResponseBodies: true,
};

export default function () {
  const res = http.get(url('/audit?limit=50'), {
    headers: JSON_HEADERS,
    tags: { type: 'read', endpoint: 'audit' },
  });
  check(res, { 'audit status 2xx': (r) => r.status >= 200 && r.status < 300 });
  sleep(1);
}
