// Browser audit entrypoint.
//   node run-browser-audit.mjs
//
// Optional env:
//   AGENTOS_AUDIT_SKIP_CATALOG_CHECK=1   — skip browser_test_README.md cross-check
//   PW_HEADLESS=false                     — run headed
//   PW_SLOWMO=200                         — slow each action
//
// Exits 0 if no FAIL, nonzero otherwise.

import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import {
  REPO_ROOT,
  RESULTS_ROOT,
  runStamp,
  writeResultFile,
} from './lib/env.mjs';
import {
  launchBrowser,
  newContext,
  saveFailureArtifacts,
} from './lib/browser.mjs';
import { SUPPORTED_BROWSER_AUDIT_IDS } from './browser-audit-scope.mjs';

import { runFlow as smokeFlow } from './flows/smoke.mjs';
import { runFlow as dashboardFlow } from './flows/dashboard.mjs';
import { runFlow as contextFlow } from './flows/context.mjs';
import { runFlow as memoryFlow } from './flows/memory.mjs';
import { runFlow as adaptersFlow } from './flows/adapters.mjs';
import { runFlow as policiesFlow } from './flows/policies.mjs';
import { runFlow as skillsFlow } from './flows/skills.mjs';
import { runFlow as approvalsFlow } from './flows/approvals.mjs';
import { runFlow as auditFlow } from './flows/audit.mjs';
import { runFlow as themeFlow } from './flows/theme.mjs';
import { runFlow as a11yFlow } from './flows/a11y.mjs';

const README_PATH = join(REPO_ROOT, 'browser_test_README.md');
const STAMP = runStamp();
const ID_PATTERN = /T-[A-Z0-9]+-\d+/g;

const FLOWS = [
  { name: 'smoke',     run: smokeFlow,     ids: ['T-SMK-001','T-SMK-002','T-SMK-003','T-SMK-004','T-SMK-005'] },
  { name: 'dashboard', run: dashboardFlow, ids: ['T-DASH-001','T-DASH-002'] },
  { name: 'context',   run: contextFlow,   ids: ['T-CTX-001','T-CTX-002','T-CTX-003'] },
  { name: 'memory',    run: memoryFlow,    ids: ['T-MEM-001','T-MEM-002','T-MEM-003'] },
  { name: 'adapters',  run: adaptersFlow,  ids: ['T-ADP-001','T-ADP-002'] },
  { name: 'policies',  run: policiesFlow,  ids: ['T-POL-001','T-POL-002','T-POL-003'] },
  { name: 'skills',    run: skillsFlow,    ids: ['T-SKL-001','T-SKL-002'] },
  { name: 'approvals', run: approvalsFlow, ids: ['T-APP-001','T-APP-002','T-APP-003','T-APP-004'] },
  { name: 'audit',     run: auditFlow,     ids: ['T-AUD-001','T-AUD-002','T-AUD-003'] },
  { name: 'theme',     run: themeFlow,     ids: ['T-THM-001','T-THM-002','T-THM-003','T-THM-004'] },
  { name: 'a11y',      run: a11yFlow,      ids: [
    'T-A11Y-001','T-A11Y-002','T-A11Y-003','T-A11Y-004',
    'T-A11Y-005','T-A11Y-006','T-A11Y-007','T-A11Y-008',
  ] },
];

function expectFn(condition, message) {
  if (!condition) throw new Error(message);
}

function escapeMdCell(value) {
  return String(value).replace(/\|/g, '\\|').replace(/\n/g, ' ');
}

function crossCheckCatalog() {
  if (process.env.AGENTOS_AUDIT_SKIP_CATALOG_CHECK === '1') return { skipped: true };
  if (!existsSync(README_PATH)) {
    throw new Error(
      `browser_test_README.md not found at ${README_PATH}. ` +
      `Set AGENTOS_AUDIT_SKIP_CATALOG_CHECK=1 to bypass during catalog development.`,
    );
  }
  const text = readFileSync(README_PATH, 'utf8');
  const documented = new Set(text.match(ID_PATTERN) ?? []);
  const missingFromReadme = SUPPORTED_BROWSER_AUDIT_IDS.filter((id) => !documented.has(id));
  // The catalog (README) is allowed to be a SUPERSET of the scope: it lists every
  // ID we might test (including PLANNED ones not yet implemented in flows). The
  // scope file lists only what the harness currently exercises. The invariant
  // therefore is one-way: every scoped ID must appear in the README.
  if (missingFromReadme.length) {
    throw new Error(
      `Catalog drift: scope file references IDs missing from ${README_PATH}.\n` +
      `Missing from README: ${missingFromReadme.join(', ')}\n` +
      `(README may contain additional PLANNED IDs that are intentionally not in scope.)`,
    );
  }
  return { skipped: false };
}

class Auditor {
  constructor(ids) {
    this.results = new Map(
      ids.map((id) => [id, {
        id,
        status: 'BLOCKED',
        detail: 'Not exercised.',
        evidence: null,
      }]),
    );
  }

  set(id, status, detail, evidence = null) {
    if (!this.results.has(id)) {
      this.results.set(id, { id, status, detail, evidence });
      return;
    }
    this.results.set(id, { id, status, detail, evidence });
  }

  bulkBlock(ids, detail) {
    for (const id of ids) {
      const cur = this.results.get(id);
      // Only mark as BLOCKED if not already executed.
      if (!cur || cur.status === 'BLOCKED') {
        this.set(id, 'BLOCKED', detail);
      }
    }
  }

  summary() {
    const counts = { PASS: 0, FAIL: 0, BLOCKED: 0 };
    for (const r of this.results.values()) {
      counts[r.status] = (counts[r.status] ?? 0) + 1;
    }
    return counts;
  }

  toJson() {
    return {
      run_at: new Date().toISOString(),
      scope: 'agentic-os-browser-audit',
      summary: this.summary(),
      results: [...this.results.values()].sort((a, b) => a.id.localeCompare(b.id)),
    };
  }

  toMarkdown() {
    const counts = this.summary();
    const lines = [
      '# Agentic OS — Browser Audit Results',
      '',
      `Run: ${new Date().toISOString()}`,
      '',
      `Summary: PASS ${counts.PASS}, FAIL ${counts.FAIL}, BLOCKED ${counts.BLOCKED}`,
      '',
      '| ID | Status | Detail |',
      '|---|---|---|',
    ];
    for (const r of [...this.results.values()].sort((a, b) => a.id.localeCompare(b.id))) {
      const detail = r.evidence
        ? `${r.detail} (evidence: ${r.evidence})`
        : r.detail;
      lines.push(`| ${r.id} | ${r.status} | ${escapeMdCell(detail)} |`);
    }
    return lines.join('\n') + '\n';
  }
}

function buildExpect(page, auditor) {
  const recorded = new Set();
  // The synchronous `expect(cond, msg)` form mirrors the reference impl.
  const expect = (cond, message) => expectFn(cond, message);
  // Each step wraps a single test ID's body, records PASS/FAIL, and never aborts the flow.
  expect.step = async (id, description, body) => {
    recorded.add(id);
    try {
      await body();
      auditor.set(id, 'PASS', description);
    } catch (err) {
      const message = err && err.message ? err.message : String(err);
      let evidence = null;
      try {
        const { imagePath } = await saveFailureArtifacts(page, id, `${id} ${description}\n${message}\n${err && err.stack ? err.stack : ''}`);
        evidence = imagePath;
      } catch {
        evidence = null;
      }
      auditor.set(id, 'FAIL', `${description} — ${message}`, evidence);
    }
  };
  expect.recorded = recorded;
  return expect;
}

async function runOneFlow(browser, auditor, flow) {
  const context = await newContext(browser);
  const page = await context.newPage();
  const expect = buildExpect(page, auditor);
  try {
    await flow.run({ page, expect, ids: flow.ids });
  } catch (err) {
    // Unhandled in-flow exception: mark any IDs not yet executed as BLOCKED.
    const message = err && err.message ? err.message : String(err);
    let evidence = null;
    try {
      const { imagePath } = await saveFailureArtifacts(page, `${flow.name}-unhandled`, message);
      evidence = imagePath;
    } catch {
      evidence = null;
    }
    for (const id of flow.ids) {
      if (!expect.recorded.has(id)) {
        auditor.set(id, 'BLOCKED', `flow "${flow.name}" aborted before this step: ${message}`, evidence);
      }
    }
  } finally {
    await context.close().catch(() => {});
  }
}

async function main() {
  const catalog = crossCheckCatalog();
  const auditor = new Auditor(SUPPORTED_BROWSER_AUDIT_IDS);
  const browser = await launchBrowser();
  try {
    for (const flow of FLOWS) {
      console.error(`[flow] ${flow.name} (${flow.ids.length} ids)`);
      await runOneFlow(browser, auditor, flow);
    }
  } finally {
    await browser.close().catch(() => {});
  }

  const json = auditor.toJson();
  const md = auditor.toMarkdown();
  const jsonPath = writeResultFile(`browser-audit-strict-${STAMP}.json`, JSON.stringify(json, null, 2));
  const mdPath   = writeResultFile(`browser-audit-strict-${STAMP}.md`,   md);

  console.log(`results_root=${RESULTS_ROOT}`);
  console.log(`json=${jsonPath}`);
  console.log(`md=${mdPath}`);
  console.log(`summary=${JSON.stringify(json.summary)}`);
  if (catalog.skipped) console.log('catalog_cross_check=SKIPPED');

  if (json.summary.FAIL > 0) process.exitCode = 1;
}

main().catch((err) => {
  console.error(err);
  process.exitCode = 2;
});
