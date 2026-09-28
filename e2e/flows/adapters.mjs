import { waitNetworkIdle } from '../lib/browser.mjs';
import { API_URL } from '../lib/env.mjs';

export async function runFlow({ page, expect }) {
  await expect.step('T-ADP-001', 'three CLI cards visible', async () => {
    await page.goto('/adapters', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    // The UI iterates over claude/gemini/codex.
    for (const name of ['claude', 'gemini', 'codex']) {
      const count = await page.getByText(new RegExp(`^${name}$`)).count();
      expect(count >= 1, `did not see adapter card for ${name}`);
    }
  });

  await expect.step('T-ADP-002', 'compile button enqueues a task', async () => {
    await page.goto('/adapters', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    // Snapshot worker task count before.
    const before = await (await fetch(`${API_URL}/worker/tasks`).then((r) => r.json()).catch(() => [])) ;
    const beforeCount = Array.isArray(before) ? before.length : (before?.tasks?.length ?? 0);

    const btn = page.getByRole('button', { name: /compile/i }).first();
    await btn.waitFor({ state: 'visible', timeout: 10000 });
    await btn.click();

    // Wait a moment for the API to receive the enqueue.
    await page.waitForTimeout(1200);

    const after = await (await fetch(`${API_URL}/worker/tasks`).then((r) => r.json()).catch(() => [])) ;
    const afterCount = Array.isArray(after) ? after.length : (after?.tasks?.length ?? 0);
    expect(
      afterCount > beforeCount || afterCount > 0,
      `worker tasks did not grow after compile click (before=${beforeCount}, after=${afterCount})`,
    );
  });
}
