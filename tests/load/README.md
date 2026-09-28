# AgenticOS Load & Performance Suite (k6)

This directory contains [k6](https://k6.io) scripts that exercise the
FastAPI backend at staged concurrency and assert latency / memory budgets.

## Install k6 (Linux / Debian / Ubuntu)

```bash
sudo gpg -k
sudo gpg --no-default-keyring \
  --keyring /usr/share/keyrings/k6-archive-keyring.gpg \
  --keyserver hkp://keyserver.ubuntu.com:80 \
  --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" \
  | sudo tee /etc/apt/sources.list.d/k6.list
sudo apt-get update
sudo apt-get install k6
```

macOS: `brew install k6`. Other platforms: see <https://grafana.com/docs/k6/latest/set-up/install-k6/>.

If `k6` is not on `PATH`, `make load` (and `run_all.sh`) will report
`BLOCKED: k6 not installed` and exit 0 rather than hard-failing.

## Environment variables

| Variable       | Default                   | Purpose                                          |
| -------------- | ------------------------- | ------------------------------------------------ |
| `BASE_URL`     | `http://localhost:8000`   | Backend root URL.                                |
| `PROJECT_SLUG` | `default`                 | Project slug used by memory + approvals scripts. |

## Scenarios

| Script             | Endpoint(s)                                       | Profile                  | Budget                |
| ------------------ | ------------------------------------------------- | ------------------------ | --------------------- |
| `audit.js`         | `GET /audit?limit=50`                             | ramp 10 / 100 / 500 VUs  | read p95 < 300 ms     |
| `memory_search.js` | `POST /projects/{slug}/memory/search/semantic`    | ramp 10 / 100 / 500 VUs  | embedding p95 < 800 ms|
| `approvals.js`     | `GET /approvals` (70%), `POST /approvals` (30%)   | ramp 10 / 100 / 500 VUs  | read p95 < 300 ms, write p95 < 1000 ms |
| `memory_leak.js`   | `GET /audit?limit=20` at constant 50 RPS for 5 m  | 5-minute sustained 50 RPS| final RSS < 2x baseline |

### Staged ramp profile (audit / memory_search / approvals)

```
30s ramp  0 -> 10 VUs
 1m hold  10 VUs
30s ramp  10 -> 100 VUs
 1m hold  100 VUs
30s ramp  100 -> 500 VUs
 1m hold  500 VUs
15s ramp  500 -> 0 VUs    (cooldown)
```

Total wall time per ramped script: ~5 minutes.

### Memory-leak detector

`memory_leak.js` uses k6's `constant-arrival-rate` executor to drive a
deterministic 50 RPS for 5 minutes. `setup()` captures a baseline RSS by
probing (in order) `GET /metrics` (Prometheus
`process_resident_memory_bytes`) then `GET /health/rss` (JSON `{rss: bytes}`).
`teardown()` re-reads RSS and prints:

```
MEMORY_LEAK_CHECK: baseline=<B> final=<F> ratio=<F/B> PASS|FAIL
```

If neither RSS endpoint is exposed, the assertion is **SKIPPED** (not
failed) and the line is logged with `SKIPPED`.

## Budget summary

| Class      | p95 budget |
| ---------- | ---------- |
| Reads      | < 300 ms   |
| Writes     | < 1000 ms  |
| Embedding  | < 800 ms   |
| Memory RSS | final < 2x idle baseline (sustained 50 RPS, 5 min) |

## Running

Whole suite (used by `make load`):

```bash
bash tests/load/run_all.sh
# or, from repo root:
make load
```

Individual scripts:

```bash
BASE_URL=http://localhost:8000 PROJECT_SLUG=default k6 run tests/load/audit.js
k6 run tests/load/memory_search.js
k6 run tests/load/approvals.js
k6 run tests/load/memory_leak.js
```

Tip: pipe results into a JSON summary for CI:

```bash
k6 run --summary-export=audit.summary.json tests/load/audit.js
```

## Notes

- The backend must be running and reachable at `BASE_URL`. Use
  `docker-compose up` (or `agentos serve`) before invoking the suite.
- 500-VU stages are intentionally aggressive; on a laptop you may want to
  scale `STAGED_RAMP` down in `common.js` (or run individual scripts with
  `--vus`/`--stage` overrides).
- `approvals.js` sends both the spec-style fields (`title`, `kind`,
  `payload`) and the schema-required fields (`tool`, `action`, `raw_input`)
  so the script works against the current backend without further changes.
