import { waitNetworkIdle, runAxe } from '../lib/browser.mjs';

const ROUTES = [
  { id: 'T-A11Y-001', path: '/' },
  { id: 'T-A11Y-002', path: '/context' },
  { id: 'T-A11Y-003', path: '/memory' },
  { id: 'T-A11Y-004', path: '/adapters' },
  { id: 'T-A11Y-005', path: '/policies' },
  { id: 'T-A11Y-006', path: '/skills' },
  { id: 'T-A11Y-007', path: '/approvals' },
  { id: 'T-A11Y-008', path: '/audit' },
];

// Only "critical" impact axe violations block CI. Serious findings (e.g.
// color-contrast) are still reported in the artifact for tracking but do not
// fail the build. Rationale: color-contrast often produces dozens of findings
// per route on a custom dark theme; bundling them as blockers gates every merge
// on a known-tracked debt backlog. Critical = label/name/keyboard-trap — those
// genuinely break the page for assistive-tech users and must be zero.
const BLOCKING = new Set(['critical']);
const TRACKED = new Set(['serious']);

export async function runFlow({ page, expect }) {
  for (const route of ROUTES) {
    await expect.step(route.id, `axe scan of ${route.path}`, async () => {
      await page.goto(route.path, { waitUntil: 'domcontentloaded' });
      await waitNetworkIdle(page);
      const violations = await runAxe(page, route.id);
      const blocking = violations.filter((v) => BLOCKING.has(v.impact));
      const tracked = violations.filter((v) => TRACKED.has(v.impact));
      const blockingSummary = blocking
        .map((v) => `${v.id}(${v.impact}, ${v.nodes.length})`)
        .join('; ');
      const trackedSummary = tracked
        .map((v) => `${v.id}(${v.impact}, ${v.nodes.length})`)
        .join('; ');
      // Tracked-but-non-blocking findings are appended to the failure message
      // when blocking violations also exist; otherwise the test passes and the
      // tracked findings are logged via runAxe's evidence writer.
      const note = trackedSummary ? ` [tracked: ${trackedSummary}]` : '';
      expect(blocking.length === 0, `axe critical violations on ${route.path}: ${blockingSummary || '(none)'}${note}`);
    });
  }
}
