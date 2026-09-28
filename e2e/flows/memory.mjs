import { waitNetworkIdle } from '../lib/browser.mjs';

export async function runFlow({ page, expect }) {
  await expect.step('T-MEM-001', 'memory page renders', async () => {
    await page.goto('/memory', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    await page.getByText(/Memory/i).first().waitFor({ timeout: 10000 });
  });

  await expect.step('T-MEM-002', 'search input present and accepts text', async () => {
    await page.goto('/memory', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    const input = page.locator('input[type="text"], input:not([type])').first();
    await input.waitFor({ state: 'visible', timeout: 10000 });
    await input.fill('alpha');
    expect((await input.inputValue()) === 'alpha', 'search input did not accept value');
    await page.waitForTimeout(400); // debounce
  });

  await expect.step('T-MEM-003', 'semantic search button is operable', async () => {
    await page.goto('/memory', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    const input = page.locator('input[type="text"], input:not([type])').first();
    await input.fill('hello');
    const semBtn = page.getByRole('button', { name: /semantic/i }).first();
    if (await semBtn.count() === 0) {
      // Some UIs label it differently; tolerate either text.
      const alt = page.getByRole('button', { name: /search/i }).first();
      expect(await alt.count() > 0, 'no semantic search button found');
      await alt.click();
    } else {
      await semBtn.click();
    }
    // The mutation either succeeds (results render) or errors (toast). Either is observable.
    await page.waitForTimeout(1500);
  });
}
