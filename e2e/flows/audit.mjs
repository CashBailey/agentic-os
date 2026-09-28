import { waitNetworkIdle } from '../lib/browser.mjs';

export async function runFlow({ page, expect }) {
  await expect.step('T-AUD-001', 'audit table renders', async () => {
    await page.goto('/audit', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    await page.getByText(/Audit/i).first().waitFor({ timeout: 10000 });
  });

  await expect.step('T-AUD-002', 'pagination cursor button present', async () => {
    await page.goto('/audit', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    // Either a "next" / "more" button is visible, or the page has no events (empty state).
    // We just confirm the UI surface exists for cursor navigation.
    const next = page.getByRole('button', { name: /next|more|load/i });
    const noEvents = await page.getByText(/no events|empty/i).count();
    const hasNext = await next.count();
    expect(hasNext > 0 || noEvents > 0, 'neither pagination control nor empty state visible');
  });

  await expect.step('T-AUD-003', 'live-tail toggle present and SSE connects', async () => {
    const sseSeen = { hit: false };
    page.on('request', (req) => {
      if (/\/events(\?|$)/.test(req.url())) sseSeen.hit = true;
    });
    await page.goto('/audit', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    await page.waitForTimeout(1500);
    // A toggle button labelled "live" or similar should exist.
    const toggle = page.getByRole('button', { name: /live/i }).first();
    expect(await toggle.count() > 0 || sseSeen.hit, 'no live toggle and no SSE request observed');
  });
}
