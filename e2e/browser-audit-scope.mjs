// Browser-auditable IDs only. The README maintained by catalog-author must
// list every ID below; run-browser-audit.mjs fails loud on drift.
//
// Prefix legend:
//   T-SMK   smoke (boot, nav, dashboard, theme, project switcher)
//   T-DASH  dashboard (CLI cards, offline banner)
//   T-CTX   context editor
//   T-MEM   memory (list, search, semantic)
//   T-ADP   adapters (cards, compile enqueue)
//   T-POL   policies (list, edit, simulator)
//   T-SKL   skills+workflows (list, tab switch)
//   T-APP   approvals (table, approve, deny, SSE)
//   T-AUD   audit (cursor, live tail, payload expand)
//   T-THM   theme (default, toggle, persistence)
//   T-A11Y  axe scan per route

export const SUPPORTED_BROWSER_AUDIT_IDS = Object.freeze([
  // Smoke
  'T-SMK-001',
  'T-SMK-002',
  'T-SMK-003',
  'T-SMK-004',
  'T-SMK-005',
  // Dashboard
  'T-DASH-001',
  'T-DASH-002',
  // Context
  'T-CTX-001',
  'T-CTX-002',
  'T-CTX-003',
  // Memory
  'T-MEM-001',
  'T-MEM-002',
  'T-MEM-003',
  // Adapters
  'T-ADP-001',
  'T-ADP-002',
  // Policies
  'T-POL-001',
  'T-POL-002',
  'T-POL-003',
  // Skills + workflows
  'T-SKL-001',
  'T-SKL-002',
  // Approvals
  'T-APP-001',
  'T-APP-002',
  'T-APP-003',
  'T-APP-004',
  // Audit
  'T-AUD-001',
  'T-AUD-002',
  'T-AUD-003',
  // Theme
  'T-THM-001',
  'T-THM-002',
  'T-THM-003',
  'T-THM-004',
  // A11y (per-route axe)
  'T-A11Y-001',
  'T-A11Y-002',
  'T-A11Y-003',
  'T-A11Y-004',
  'T-A11Y-005',
  'T-A11Y-006',
  'T-A11Y-007',
  'T-A11Y-008',
]);
