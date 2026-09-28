// Memory-leak detector: 5 minutes sustained 50 RPS, assert backend RSS < 2x baseline.
//
// Tries /metrics (Prometheus exposition: process_resident_memory_bytes) first,
// then falls back to /health/rss (expects JSON {rss: <bytes>}). If neither
// endpoint is available, the RSS assertion is SKIPPED (not failed) and the
// load itself still runs.

import http from 'k6/http';
import { check } from 'k6';
import { JSON_HEADERS, url } from './common.js';

export const options = {
  scenarios: {
    sustained: {
      executor: 'constant-arrival-rate',
      rate: 50,
      timeUnit: '1s',
      duration: '5m',
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
  },
  thresholds: {
    'http_req_duration{type:read}': ['p(95)<300'],
    'http_req_failed': ['rate<0.02'],
  },
  discardResponseBodies: true,
};

function parsePrometheusRss(body) {
  // process_resident_memory_bytes <value>
  const m = body.match(/^process_resident_memory_bytes\s+([0-9.eE+-]+)/m);
  if (!m) return null;
  const v = Number(m[1]);
  return Number.isFinite(v) ? v : null;
}

function parseJsonRss(body) {
  try {
    const o = JSON.parse(body);
    const candidates = [o.rss, o.rss_bytes, o.memory_rss, o.process_resident_memory_bytes];
    for (const c of candidates) {
      const v = Number(c);
      if (Number.isFinite(v) && v > 0) return v;
    }
  } catch (_e) { /* ignore */ }
  return null;
}

function fetchRss() {
  // Try Prometheus /metrics first.
  let res = http.get(url('/metrics'), { headers: { Accept: 'text/plain' } });
  if (res.status >= 200 && res.status < 300) {
    const v = parsePrometheusRss(res.body || '');
    if (v !== null) return { source: '/metrics', value: v };
  }
  // Fall back to /health/rss.
  res = http.get(url('/health/rss'), { headers: JSON_HEADERS });
  if (res.status >= 200 && res.status < 300) {
    const v = parseJsonRss(res.body || '');
    if (v !== null) return { source: '/health/rss', value: v };
  }
  return null;
}

export function setup() {
  const rss = fetchRss();
  if (!rss) {
    console.log('rss-unavailable: neither /metrics nor /health/rss exposed parseable RSS');
    return { baseline: null, source: null };
  }
  console.log(`MEMORY_LEAK_BASELINE: source=${rss.source} rss=${rss.value}`);
  return { baseline: rss.value, source: rss.source };
}

export default function () {
  const res = http.get(url('/audit?limit=20'), {
    headers: JSON_HEADERS,
    tags: { type: 'read', endpoint: 'audit_leak' },
  });
  check(res, { 'audit 2xx (leak)': (r) => r.status >= 200 && r.status < 300 });
}

export function teardown(data) {
  if (data == null || data.baseline == null) {
    console.log('MEMORY_LEAK_CHECK: baseline=NA final=NA ratio=NA SKIPPED (rss endpoint unavailable)');
    return;
  }
  const rss = fetchRss();
  if (!rss) {
    console.log(`MEMORY_LEAK_CHECK: baseline=${data.baseline} final=NA ratio=NA SKIPPED (final rss unavailable)`);
    return;
  }
  const ratio = rss.value / data.baseline;
  const verdict = ratio < 2.0 ? 'PASS' : 'FAIL';
  console.log(
    `MEMORY_LEAK_CHECK: baseline=${data.baseline} final=${rss.value} ratio=${ratio.toFixed(3)} ${verdict}`
  );
  if (verdict === 'FAIL') {
    // Non-zero exit via thrown error so 'k6 run' reports failure.
    throw new Error(`Memory leak suspected: final RSS ${rss.value} >= 2x baseline ${data.baseline}`);
  }
}
