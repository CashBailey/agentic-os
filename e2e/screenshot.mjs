#!/usr/bin/env node
// Ad-hoc screenshot CLI:
//   node screenshot.mjs --route /memory [--theme dark|light] [--out path]
//                       [--no-full-page] [--selector "css"]
// Prints absolute output path to stdout.
import { resolve, join } from 'node:path';
import { mkdirSync } from 'node:fs';
import { launchBrowser, newContext, setTheme, waitNetworkIdle } from './lib/browser.mjs';
import { RESULTS_ROOT, runStamp, safeSlug } from './lib/env.mjs';

function parseArgs(argv) {
  const out = { fullPage: true };
  for (let i = 0; i < argv.length; i += 1) {
    const a = argv[i];
    const next = () => argv[++i];
    if (a === '--route') out.route = next();
    else if (a === '--theme') out.theme = next();
    else if (a === '--out') out.out = next();
    else if (a === '--selector') out.selector = next();
    else if (a === '--full-page') out.fullPage = true;
    else if (a === '--no-full-page') out.fullPage = false;
    else if (a === '--help' || a === '-h') out.help = true;
  }
  return out;
}

function usage() {
  console.error(
    'usage: node screenshot.mjs --route <path> [--theme dark|light] [--out file] [--no-full-page] [--selector css]',
  );
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.help) { usage(); process.exit(0); }
  if (!args.route) { usage(); process.exit(2); }
  if (args.theme && !['dark', 'light'].includes(args.theme)) {
    console.error(`--theme must be dark or light, got "${args.theme}"`); process.exit(2);
  }

  const browser = await launchBrowser();
  const context = await newContext(browser);
  const page = await context.newPage();
  try {
    await page.goto(args.route, { waitUntil: 'domcontentloaded' });
    await waitNetworkIdle(page);
    if (args.theme) {
      await setTheme(page, args.theme);
    }
    const effectiveTheme = args.theme
      || (await page.evaluate(() => document.documentElement.getAttribute('data-theme')))
      || 'unknown';

    let outPath;
    if (args.out) {
      outPath = resolve(args.out);
      mkdirSync(resolve(outPath, '..'), { recursive: true });
    } else {
      outPath = join(
        RESULTS_ROOT,
        `screenshot-${safeSlug(args.route)}-${effectiveTheme}-${runStamp()}.png`,
      );
    }

    if (args.selector) {
      const el = await page.$(args.selector);
      if (!el) throw new Error(`selector not found: ${args.selector}`);
      await el.screenshot({ path: outPath });
    } else {
      await page.screenshot({ path: outPath, fullPage: args.fullPage !== false });
    }
    process.stdout.write(`${outPath}\n`);
  } finally {
    await context.close().catch(() => {});
    await browser.close().catch(() => {});
  }
}

main().catch((err) => { console.error(err); process.exit(1); });
