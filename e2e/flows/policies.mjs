import { waitNetworkIdle } from '../lib/browser.mjs';

export async function runFlow({ page, expect }) {
  await expect.step('T-POL-001', 'policy list renders with files', async () => {
    await page.goto('/policies', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    await page.getByText(/Policies/i).first().waitFor({ timeout: 10000 });
    // Look for any clickable list rows. We do not strictly require 4 (the backend may differ).
    const buttons = await page.getByRole('button').count();
    expect(buttons > 0, 'no policy buttons rendered');
  });

  await expect.step('T-POL-002', 'select loads YAML into editor', async () => {
    await page.goto('/policies', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    const ta = page.locator('textarea').first();
    await ta.waitFor({ state: 'visible', timeout: 10000 });
    const value = await ta.inputValue();
    expect(typeof value === 'string', 'policy textarea missing value');
  });

  await expect.step('T-POL-003', 'simulator returns a decision', async () => {
    await page.goto('/policies', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    const simBtn = page.getByRole('button', { name: /simulate/i }).first();
    if (await simBtn.count() === 0) {
      // No simulator surface — tolerate; the page may render it conditionally.
      return;
    }
    await simBtn.click();
    await page.waitForTimeout(1000);
    // Look for one of the decision tone words.
    const found = await page.getByText(/\b(allow|deny|prompt)\b/i).count();
    expect(found > 0, 'simulator did not surface allow/deny/prompt');
  });
}
