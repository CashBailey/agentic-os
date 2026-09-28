import { fileURLToPath } from 'node:url';
import { dirname, join, resolve } from 'node:path';
import { mkdirSync, writeFileSync } from 'node:fs';

const HERE = dirname(fileURLToPath(import.meta.url));
export const REPO_ROOT = resolve(HERE, '..', '..');
export const E2E_ROOT = resolve(HERE, '..');
export const RESULTS_ROOT = join(E2E_ROOT, 'results');

mkdirSync(RESULTS_ROOT, { recursive: true });

export const BASE_URL =
  process.env.AGENTOS_FRONTEND_URL ?? 'http://localhost:5173';
export const API_URL =
  process.env.AGENTOS_API_URL ?? 'http://127.0.0.1:8765';

export function runStamp() {
  return new Date().toISOString().replace(/[:.]/g, '-');
}

export function writeResultFile(name, content) {
  const path = join(RESULTS_ROOT, name);
  writeFileSync(path, content);
  return path;
}

export function safeSlug(value) {
  return String(value)
    .replace(/^\/+|\/+$/g, '')
    .replace(/[^a-zA-Z0-9_-]+/g, '_')
    || 'root';
}
