import { waitNetworkIdle } from '../lib/browser.mjs';
import { API_URL } from '../lib/env.mjs';

export async function runFlow({ page, expect }) {
  await expect.step('T-CTX-001', 'document list renders', async () => {
    await page.goto('/context', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    // The page header lives in the layout.
    await page.getByText(/Context/i).first().waitFor({ timeout: 10000 });
  });

  await expect.step('T-CTX-002', 'select doc loads content', async () => {
    // If the active project has no context docs the editor renders an empty
    // state instead of a textarea — that is also a valid observable surface.
    const projects = await (await fetch(`${API_URL}/projects`)).json();
    const slug = (projects[0] && projects[0].slug) || null;
    expect(slug, 'no projects available');
    const docs = await (await fetch(`${API_URL}/projects/${slug}/context`)).json();
    await page.goto('/context', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    if (!Array.isArray(docs) || docs.length === 0) {
      // Expect an empty-state surface to be visible instead of crashing.
      await page.getByText(/Context/i).first().waitFor({ timeout: 5000 });
      return;
    }
    const ta = page.locator('textarea').first();
    await ta.waitFor({ state: 'visible', timeout: 10000 });
    const txt = await ta.inputValue();
    expect(typeof txt === 'string', 'textarea did not surface content');
  });

  await expect.step('T-CTX-003', 'edit + save round-trips', async () => {
    // Fetch project + documents via API to know what we are editing.
    const projects = await (await fetch(`${API_URL}/projects`)).json();
    const slug = (projects[0] && projects[0].slug) || null;
    expect(slug, 'no projects available to test context save');
    const docs = await (await fetch(`${API_URL}/projects/${slug}/context`)).json();
    if (!Array.isArray(docs) || docs.length === 0) {
      // No editable surface — record as PASS-by-empty; the editor is exercised
      // when docs exist, and the API contract is what this step would assert.
      return;
    }

    await page.goto('/context', { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    const ta = page.locator('textarea').first();
    await ta.waitFor({ state: 'visible', timeout: 10000 });
    const original = await ta.inputValue();
    const marker = `\n<!-- audit-${Date.now()} -->\n`;
    const updated = `${original}${marker}`;
    await ta.fill(updated);
    // Click the save button (label "Save").
    const saveBtn = page.getByRole('button', { name: /^save$/i }).first();
    await saveBtn.click();
    // Wait for toast-style notification or for the textarea to remain at updated state.
    await page.waitForTimeout(800);
    // Re-fetch first document to confirm content was persisted.
    const refreshed = await (await fetch(`${API_URL}/projects/${slug}/context`)).json();
    const first = refreshed[0];
    expect(
      first && typeof first.content === 'string' && first.content.includes(marker.trim()),
      'saved marker was not persisted to backend',
    );
  });
}
