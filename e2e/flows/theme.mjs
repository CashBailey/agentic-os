import { waitNetworkIdle, setTheme } from '../lib/browser.mjs';

export async function runFlow({ page, expect }) {
  await expect.step('T-THM-001', 'dark default on fresh load', async () => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await page.evaluate(() => { try { window.localStorage.removeItem('agentos:theme'); } catch { /* ignore */ } });
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    const t = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    expect(t === 'dark', `expected dark default, got ${t}`);
  });

  await expect.step('T-THM-002', 'toggle to light updates data-theme', async () => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    await setTheme(page, 'light');
    const t = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    expect(t === 'light', `toggle did not switch to light, got ${t}`);
  });

  await expect.step('T-THM-003', 'reload persists chosen theme', async () => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    await setTheme(page, 'light');
    await page.reload({ waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    const t = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    expect(t === 'light', `light did not persist across reload, got ${t}`);
  });

  await expect.step('T-THM-004', 'toggle back to dark', async () => {
    await page.goto('/', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    await setTheme(page, 'dark');
    const t = await page.evaluate(() => document.documentElement.getAttribute('data-theme'));
    expect(t === 'dark', `did not toggle back to dark, got ${t}`);
  });
}
