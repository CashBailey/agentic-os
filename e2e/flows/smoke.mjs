import { waitNetworkIdle, setTheme } from '../lib/browser.mjs';

const ROUTES = ['/', '/context', '/memory', '/adapters', '/policies', '/skills', '/approvals', '/audit'];

export async function runFlow({ page, expect /* , ids */ }) {
  // T-SMK-001: app boots at /
  await expect.step('T-SMK-001', 'app boots at /', async () => {
    const response = await page.goto('/', { waitUntil: 'domcontentloaded' });
    expect(response && response.status() < 400, `boot returned ${response && response.status()}`);
    await waitNetworkIdle(page);
    // The sidebar brand text should appear.
    await page.getByText(/Agentic OS/).first().waitFor({ timeout: 10000 });
  });

  // T-SMK-002: nav each of the 8 routes renders without obvious error.
  await expect.step('T-SMK-002', 'each of 8 routes renders', async () => {
    for (const route of ROUTES) {
      const resp = await page.goto(route, { waitUntil: 'domcontentloaded' });
      expect(resp && resp.status() < 400, `${route} status ${resp && resp.status()}`);
      await waitNetworkIdle(page, 2000);
      // The sidebar should still be visible (app shell rendered).
      const sidebarHit = await page.getByText('control plane').count();
      expect(sidebarHit > 0, `${route} did not render app shell`);
      // No top-level toast labelled "error" with text "Failed to" is acceptable, but allow general ones.
    }
  });

  // T-SMK-003: theme defaults to dark.
  await expect.step('T-SMK-003', 'theme defaults dark', async () => {
    // Fresh context: clear storage and reload to confirm default.
    await page.evaluate(() => { try { window.localStorage.removeItem('agentos:theme'); } catch { /* ignore */ } });
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    const t = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    expect(t === 'dark', `expected data-theme=dark on fresh load, got ${t}`);
  });

  // T-SMK-004: theme toggle works.
  await expect.step('T-SMK-004', 'theme toggle works', async () => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    await setTheme(page, 'light');
    const after = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    expect(after === 'light', `toggle did not switch to light, got ${after}`);
    await setTheme(page, 'dark');
  });

  // T-SMK-005: project switcher visible.
  await expect.step('T-SMK-005', 'project switcher visible', async () => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    const sel = page.getByLabel('Project', { exact: true });
    await sel.waitFor({ state: 'visible', timeout: 5000 });
    expect(await sel.isVisible(), 'project select not visible');
  });
}
