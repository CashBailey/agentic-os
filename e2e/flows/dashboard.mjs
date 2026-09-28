import { waitNetworkIdle } from '../lib/browser.mjs';
import { API_URL } from '../lib/env.mjs';

export async function runFlow({ page, expect }) {
  // T-DASH-001: CLI cards render 3 items (claude, gemini, codex).
  await expect.step('T-DASH-001', '3 CLI cards render', async () => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    // Wait for either loading to finish or cards to mount.
    await page.waitForTimeout(500);
    // The CLI labels are rendered as font-mono text.
    for (const name of ['claude', 'gemini', 'codex']) {
      const count = await page.getByText(new RegExp(`^${name}$`)).count();
      expect(count >= 1, `did not see CLI card for ${name}`);
    }
  });

  // T-DASH-002: backend banner reflects API state.
  await expect.step('T-DASH-002', 'backend banner reflects API state', async () => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    // Probe the API directly via Node fetch.
    let apiUp = true;
    try {
      const res = await fetch(`${API_URL}/healthz`);
      apiUp = res.ok;
    } catch {
      apiUp = false;
    }
    // In the running-against-live-API case, the "API offline" banner must NOT be visible.
    const offlineBanner = await page.getByText(/api .*offline|backend.*offline|cannot reach api/i).count();
    if (apiUp) {
      expect(offlineBanner === 0, 'offline banner shown while API healthy');
    } else {
      expect(offlineBanner > 0, 'no offline banner shown while API down');
    }
  });
}
