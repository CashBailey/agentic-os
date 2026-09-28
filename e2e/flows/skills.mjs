import { waitNetworkIdle } from '../lib/browser.mjs';

export async function runFlow({ page, expect }) {
  await expect.step('T-SKL-001', 'skills page renders list area', async () => {
    await page.goto('/skills', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    await page.getByText(/Skills/).first().waitFor({ timeout: 10000 });
    // Tabs use role="tab" (see ui/Tabs.tsx).
    const tabs = await page.getByRole('tab').count();
    expect(tabs >= 2, `expected at least two tabs (skills + workflows), got ${tabs}`);
  });

  await expect.step('T-SKL-002', 'tab switch toggles content', async () => {
    await page.goto('/skills', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    const wfTab = page.getByRole('tab', { name: /workflows/i }).first();
    await wfTab.waitFor({ timeout: 10000 });
    await wfTab.click();
    await page.waitForTimeout(400);
    // Just confirm the click toggled aria-selected on the workflows tab.
    const sel = await wfTab.getAttribute('aria-selected');
    expect(sel === 'true', `workflows tab aria-selected expected 'true', got ${sel}`);
    const skTab = page.getByRole('tab', { name: /^skills/i }).first();
    await skTab.click();
    await page.waitForTimeout(200);
  });
}
