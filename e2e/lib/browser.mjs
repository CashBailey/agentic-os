import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import { join } from 'node:path';
import { writeFileSync } from 'node:fs';
import { BASE_URL, RESULTS_ROOT, runStamp, safeSlug } from './env.mjs';

export async function launchBrowser() {
  const headless = process.env.PW_HEADLESS !== 'false';
  const slowMo = Number(process.env.PW_SLOWMO ?? '0');
  return chromium.launch({
    headless,
    slowMo: Number.isFinite(slowMo) ? slowMo : 0,
    args: ['--ignore-certificate-errors'],
  });
}

export async function newContext(browser, options = {}) {
  return browser.newContext({
    baseURL: BASE_URL,
    ignoreHTTPSErrors: true,
    acceptDownloads: true,
    viewport: { width: 1440, height: 900 },
    ...options,
  });
}

export async function waitNetworkIdle(page, timeout = 3000) {
  try {
    await page.waitForLoadState('networkidle', { timeout });
  } catch {
    /* ignore */
  }
}

async function currentTheme(page) {
  return page
    .evaluate(() => document.documentElement.getAttribute('data-theme'))
    .catch(() => null);
}

export async function screenshot(page, slug, { fullPage = true, theme = null } = {}) {
  const t = theme || (await currentTheme(page)) || 'unknown';
  const stamp = runStamp();
  const path = join(RESULTS_ROOT, `${safeSlug(slug)}-${t}-${stamp}.png`);
  await page.screenshot({ path, fullPage });
  return path;
}

export async function saveFailureArtifacts(page, id, errorText) {
  const stamp = runStamp();
  const safeId = String(id).toLowerCase();
  const imagePath = join(RESULTS_ROOT, `fail-${safeId}-${stamp}.png`);
  const txtPath = join(RESULTS_ROOT, `fail-${safeId}-${stamp}.txt`);
  try {
    await page.screenshot({ path: imagePath, fullPage: true });
  } catch {
    /* page may be closed */
  }
  try {
    writeFileSync(txtPath, String(errorText));
  } catch {
    /* ignore */
  }
  return { imagePath, txtPath };
}

export async function runAxe(page /* , id */) {
  const results = await new AxeBuilder({ page }).analyze();
  return results.violations ?? [];
}

export async function setTheme(page, target) {
  const have = await currentTheme(page);
  if (have === target) return target;
  // The toggle is a ghost button in TopBar with aria-label "Switch to <other> theme".
  const btn = page.getByRole('button', { name: /switch to (light|dark) theme/i });
  await btn.click({ timeout: 5000 });
  await page.waitForFunction(
    (t) => document.documentElement.getAttribute('data-theme') === t,
    target,
    { timeout: 5000 },
  );
  return target;
}

export async function selectProject(page, slug) {
  const sel = page.getByLabel('Project', { exact: true });
  await sel.waitFor({ state: 'visible', timeout: 10000 });
  // Wait until options are loaded.
  await page.waitForFunction(
    () => {
      const s = document.querySelector('select[aria-label="Project"]');
      return s && s.options.length > 0 && s.options[0].value !== '';
    },
    null,
    { timeout: 10000 },
  ).catch(() => {});
  await sel.selectOption(slug);
}

export async function firstProjectSlug(page) {
  await page.waitForFunction(
    () => {
      const s = document.querySelector('select[aria-label="Project"]');
      return s && s.options.length > 0 && s.options[0].value !== '';
    },
    null,
    { timeout: 10000 },
  ).catch(() => {});
  return page.evaluate(() => {
    const s = document.querySelector('select[aria-label="Project"]');
    if (!s) return null;
    return s.value || (s.options[0] && s.options[0].value) || null;
  });
}
