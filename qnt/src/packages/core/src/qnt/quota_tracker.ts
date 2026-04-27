/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */
import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';

const QUOTA_FILE = path.join(
  os.homedir(), '.qnt', 'quota_state.json'
);

// Conservative daily limits per model
// Based on real-world Google AI Pro observations
const MODEL_DAILY_LIMITS: Record<string, number> = {
  'gemini-2.0-flash-lite-preview-02-05': 9000,
  'gemini-2.0-flash':                   1000,
  'gemini-1.5-flash':                   1000,
  'gemini-1.5-pro':                     100,
  // Catch-all for unknown models
  'default':                            200,
};

// Thresholds for switching behavior
const WARN_AT  = 0.75; // log warning at 75% used
const SWITCH_AT = 0.90; // switch model at 90% used

interface ModelQuota {
  used: number;
  limit: number;
  last_used: string;
}

interface QuotaState {
  date: string;         // YYYY-MM-DD
  models: Record<string, ModelQuota>;
}

// ──────────────────────────────────────
// Internal helpers
// ──────────────────────────────────────

function todayDate(): string {
  return new Date().toISOString().split('T')[0];
}

function freshState(): QuotaState {
  const models: Record<string, ModelQuota> = {};
  for (const [model, limit] of Object.entries(MODEL_DAILY_LIMITS)) {
    if (model === 'default') continue;
    models[model] = { used: 0, limit, last_used: '' };
  }
  return { date: todayDate(), models };
}

function loadState(): QuotaState {
  try {
    if (fs.existsSync(QUOTA_FILE)) {
      const raw = fs.readFileSync(QUOTA_FILE, 'utf-8');
      // eslint-disable-next-line @typescript-eslint/no-unsafe-type-assertion
      const state = JSON.parse(raw) as QuotaState;
      // New day — reset all counters
      if (state.date !== todayDate()) {
        return freshState();
      }
      return state;
    }
  } catch {
    // Corrupted file — start clean
  }
  return freshState();
}

function saveState(state: QuotaState): void {
  const dir = path.dirname(QUOTA_FILE);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true, mode: 0o700 });
  }
  fs.writeFileSync(
    QUOTA_FILE,
    JSON.stringify(state, null, 2),
    { encoding: 'utf-8', mode: 0o600 }
  );
}

function getLimit(model: string): number {
  return MODEL_DAILY_LIMITS[model]
    ?? MODEL_DAILY_LIMITS['default'];
}

// ──────────────────────────────────────
// Public API
// ──────────────────────────────────────

// In-memory blacklist for current session only
// (not persisted — cleared on qnt restart)
const SESSION_BLACKLIST = new Set<string>();

export function blacklistModel(model: string): void {
  SESSION_BLACKLIST.add(model);
  console.log(
    `[qnt] Model ${model} blacklisted for this session. ` +
    `(404 endpoint not available on this account)`
  );
}

export function isBlacklisted(model: string): boolean {
  return SESSION_BLACKLIST.has(model);
}

/**
 * Record one API call for a model.
 * Call this AFTER a successful API response.
 */
export function recordUsage(model: string): void {
  const state = loadState();
  if (!state.models[model]) {
    state.models[model] = {
      used: 0,
      limit: getLimit(model),
      last_used: '',
    };
  }
  state.models[model].used += 1;
  state.models[model].last_used = new Date().toISOString();
  saveState(state);
}

/**
 * Check quota status for a model.
 * Returns:
 *   'ok'        — fine to use
 *   'warn'      — approaching limit, log it
 *   'exhausted' — switch to fallback
 */
export function checkQuota(
  model: string
): 'ok' | 'warn' | 'exhausted' {
  // Blacklisted = treat as exhausted
  if (isBlacklisted(model)) return 'exhausted';

  const state = loadState();
  const entry = state.models[model];
  if (!entry) return 'ok'; // unknown model — allow

  const ratio = entry.used / entry.limit;
  if (ratio >= SWITCH_AT) return 'exhausted';
  if (ratio >= WARN_AT)   return 'warn';
  return 'ok';
}

/**
 * Get simple quota info for a single model.
 */
export function getModelQuotaInfo(model: string): string {
  const state = loadState();
  const data = state.models[model];
  if (!data) return '0%';
  const pct = Math.round((data.used / data.limit) * 100);
  return `${pct}% (${data.used}/${data.limit})`;
}

/**
 * Get full quota report as formatted string.
 * Used by /quota slash command.
 */
export function getQuotaReport(): string {
  const state = loadState();
  const lines: string[] = [
    `QNT Quota Report — ${state.date}`,
    `Resets at: midnight Pacific Time`,
    '─'.repeat(52),
  ];

  const entries = Object.entries(state.models)
    .sort(([, a], [, b]) => (b.used / b.limit) - (a.used / a.limit));

  for (const [model, data] of entries) {
    const pct = Math.round((data.used / data.limit) * 100);
    const filled = Math.floor(pct / 10);
    const bar = '█'.repeat(filled) + '░'.repeat(10 - filled);
    const status = pct >= 90 ? '🔴' : pct >= 75 ? '🟡' : '🟢';
    const shortName = model
      .replace('gemini-', '')
      .replace('-preview', '')
      .replace('-customtools', '+tools')
      .padEnd(28);
    lines.push(
      `${status} ${shortName} ${bar} ${pct}% (${data.used}/${data.limit})`
    );
  }

  lines.push('─'.repeat(52));
  lines.push('🟢 OK  🟡 >75% used  🔴 >90% — switching to fallback');
  return lines.join('\n');
}

/**
 * Mark a model as temporarily exhausted.
 * Forces immediate switch on next request.
 * Resets at midnight with the daily counter.
 */
export function markExhausted(model: string): void {
  const state = loadState();
  if (!state.models[model]) {
    state.models[model] = {
      used: 0,
      limit: getLimit(model),
      last_used: '',
    };
  }
  // Set used to limit to force exhausted status
  state.models[model].used = state.models[model].limit;
  state.models[model].last_used = new Date().toISOString();
  saveState(state);
  console.log(`[qnt] Model ${model} marked exhausted. Will use fallback.`);
}

/**
 * Get the best available model right now.
 * Walks the fallback chain until finding
 * a model with quota remaining.
 * Returns null only if ALL models exhausted.
 */
export function getBestAvailableModel(
  preferredModel: string,
  getFallbackFn: (model: string) => string | null
): string | null {
  let current: string | null = preferredModel;
  const tried = new Set<string>();

  while (current !== null) {
    if (tried.has(current)) break; // prevent infinite loop
    tried.add(current);

    const status = checkQuota(current);
    if (status !== 'exhausted') {
      return current; // found one with quota
    }

    current = getFallbackFn(current);
  }

  // All models in chain exhausted
  // Return LITE as absolute last resort
  return 'gemini-2.0-flash-lite-preview-02-05';
}
