/**
 * @license
 * Copyright 2026 Google LLC
 * SPDX-License-Identifier: Apache-2.0
 */

// Available models in priority order
export const QNT_MODELS = {
  // Tier 1 — Ultra fast, near-unlimited quota
  LITE: 'gemini-2.0-flash-lite-preview-02-05',

  // Tier 2 — Fast, high quality, ~1000/day
  FLASH: 'gemini-2.0-flash',

  // Tier 3 — Stable flash fallback
  FLASH_STABLE: 'gemini-1.5-flash',

  // Tier 4 — Most capable, ~100/day (use sparingly)
  PRO: 'gemini-2.0-flash',

  // Tier 5 — Stable pro fallback
  PRO_STABLE: 'gemini-1.5-pro',

  // Tier 6 — Emergency ultra-lite fallback
  FLASH_LITE_STABLE: 'gemini-1.5-flash',
} as const;

export type QntModel = typeof QNT_MODELS[keyof typeof QNT_MODELS];

// Fallback chain — if model quota hit or fails
// null means no further fallback available
export const FALLBACK_CHAIN: Record<string, string | null> = {
  // Tier 4 Pro chain
  'gemini-3.1-pro-preview-customtools': 'gemini-2.5-pro',
  'gemini-2.5-pro':                     'gemini-3-flash-preview',
  
  // Tier 2 Flash chain  
  'gemini-3-flash-preview':             'gemini-2.5-flash',
  'gemini-2.5-flash':                   'gemini-3.1-flash-lite-preview',
  
  // Tier 1 Lite chain (last resort)
  'gemini-3.1-flash-lite-preview':      'gemini-2.5-flash-lite',
  'gemini-2.5-flash-lite':              null,
};

/**
 * Check if error indicates model not available
 * (404 = endpoint not found for this account/tier)
 */
export function isModelUnavailableError(
  error: unknown
): boolean {
  const msg = String(error).toLowerCase();
  return (
    msg.includes('404') ||
    msg.includes('not found') ||
    msg.includes('model not found') ||
    msg.includes('not supported') ||
    msg.includes('preview') && msg.includes('access') ||
    msg.includes('cloudcode-pa.googleapis.com')
  );
}

// Keywords that classify task complexity
// Checked in order: PRO first, LITE second, FLASH default
const PRO_KEYWORDS = [
  'generate strategy', 'new strategy', 'write strategy',
  'create strategy', 'implement strategy',
  'research paper', 'find paper', 'arxiv', 'ssrn',
  'deep analysis', 'complex analysis',
  'architecture decision', 'design system',
  'walk-forward', 'monte carlo', 'backtest analysis',
  'multi-step', 'long-horizon',
];

const LITE_KEYWORDS = [
  'health check', 'is running', 'ping', 'uptime',
  'quick status', 'are you running',
  'format this', 'clean this up',
  'summarize log', 'what time',
  'list files', 'show directory',
  'yes', 'no', 'confirm', 'ok', 'done',
  'current status', 'check status', 'bot status',
  'project health', 'system status',
  'check logs', 'show logs', 'any errors',
  'summary report', 'quick report',
  'bot healthy', 'everything ok',
];

export const PERMANENTLY_UNAVAILABLE = new Set([
  'gemini-3.1-pro-preview-customtools',
]);

/**
 * Classify a prompt and return the appropriate model.
 * PRO for complex reasoning, LITE for trivial tasks,
 * FLASH (default) for everything in between.
 */
export function routeToModel(prompt: string): QntModel {
  const lower = prompt.toLowerCase().trim();

  // Check PRO patterns (complex, high-value tasks)
  if (PRO_KEYWORDS.some(kw => lower.includes(kw))) {
    const proModel = QNT_MODELS.PRO;
    // If Pro not available, use stable Pro instead
    if (PERMANENTLY_UNAVAILABLE.has(proModel)) {
      return QNT_MODELS.PRO_STABLE;
    }
    return proModel;
  }

  // Check LITE patterns (trivial, fast tasks)
  if (LITE_KEYWORDS.some(kw => lower.includes(kw))) {
    return QNT_MODELS.LITE;
  }

  // Default: FLASH — best balance for MasterBot tasks
  return QNT_MODELS.FLASH;
}

/**
 * Get the next fallback model when current fails.
 * Returns null if no fallback available.
 */
export function getFallbackModel(
  currentModel: string
): string | null {
  return FALLBACK_CHAIN[currentModel] ?? null;
}

/**
 * Check if an error is quota or rate limit related.
 */
export function isQuotaError(error: unknown): boolean {
  const msg = String(error).toLowerCase();
  return (
    msg.includes('429') ||
    msg.includes('quota') ||
    msg.includes('rate limit') ||
    msg.includes('resource_exhausted') ||
    msg.includes('resource exhausted') ||
    msg.includes('too many requests')
  );
}
