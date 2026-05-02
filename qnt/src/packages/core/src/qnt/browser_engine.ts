/**
 * QNT Browser Engine
 * Heavy browser automation for MasterBot intelligence.
 * Runs on M2 (16GB RAM). Results sync to M1.
 *
 * Capabilities:
 * - Full JavaScript rendering
 * - Dynamic content extraction
 * - Screenshot capture + text description
 * - Form interaction
 * - Multi-page navigation
 */

import * as fs from 'node:fs';
import * as path from 'node:path';
import * as os from 'node:os';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);

// Dynamic import — works with both puppeteer variants
let puppeteerModule: any;
try {
  puppeteerModule = require('puppeteer');
} catch {
  try {
    puppeteerModule = require('puppeteer-core');
  } catch {
    puppeteerModule = null;
  }
}

const OUTPUT_DIR = path.join(
  os.homedir(),
  'masterbot', 'qnt', 'browser_output'
);

// Chrome executable paths to try (macOS M2)
const CHROME_PATHS = [
  '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
  '/Applications/Chromium.app/Contents/MacOS/Chromium',
  path.join(os.homedir(), '.cache/puppeteer/chrome/mac_arm-147.0.7727.57/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing'),
  '/usr/bin/chromium-browser',
  '/usr/bin/chromium',
];

function findChrome(): string | undefined {
  for (const p of CHROME_PATHS) {
    if (fs.existsSync(p)) return p;
  }
  return undefined;
}

// Browser instance (reused across calls)
let browser: any = null;

/**
 * Get or create browser instance.
 * Reuses same Chrome for efficiency.
 */
export async function getBrowser(): Promise<any> {
  if (!puppeteerModule) {
    throw new Error(
      '[qnt] Browser engine not available. ' +
      'Run: npm install puppeteer (on M2)'
    );
  }

  if (browser && browser.isConnected()) {
    return browser;
  }

  const launchOptions: any = {
    headless: true,
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-dev-shm-usage',
      '--disable-gpu',
      '--disable-extensions',
      '--no-first-run',
      '--disable-background-timer-throttling',
      '--window-size=1280,900',
    ],
    defaultViewport: { width: 1280, height: 900 },
    timeout: 30000,
  };

  // Use system Chrome if available (faster launch)
  const chromePath = findChrome();
  if (chromePath) {
    launchOptions.executablePath = chromePath;
  }

  browser = await puppeteerModule.launch(launchOptions);
  return browser;
}

/**
 * Close browser cleanly.
 */
export async function closeBrowser(): Promise<void> {
  if (browser) {
    await browser.close().catch(() => null);
    browser = null;
    // Force exit if this was called from a standalone script
    if (process.send === undefined) {
       setTimeout(() => process.exit(0), 1000);
    }
  }
}

/**
 * Extract clean text content from any URL.
 * Handles JavaScript-rendered content.
 */
export async function extractText(
  url: string,
  waitSelector?: string,
  timeout = 30000
): Promise<string> {
  const b = await getBrowser();
  const page = await b.newPage();

  try {
    // Set realistic user agent
    await page.setUserAgent(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ' +
      'AppleWebKit/537.36 (KHTML, like Gecko) ' +
      'Chrome/120.0.0.0 Safari/537.36'
    );

    // Block images/fonts to speed up load
    await page.setRequestInterception(true);
    page.on('request', (req: any) => {
      const type = req.resourceType();
      if (['image', 'font', 'media'].includes(type)) {
        req.abort();
      } else {
        req.continue();
      }
    });

    await page.goto(url, {
      waitUntil: 'networkidle2',
      timeout,
    });

    // Wait for specific element if requested
    if (waitSelector) {
      await page.waitForSelector(waitSelector, {
        timeout: 10000,
      }).catch(() => null); // don't fail if not found
    }

    // Extract clean text from page
    const text: string = await page.evaluate(() => {
      // Remove noise elements
      const noise = [
        'script', 'style', 'nav', 'footer',
        'header', 'iframe', 'noscript',
        '.cookie-banner', '.ad', '.advertisement',
        '#cookie-notice', '.popup',
      ];
      noise.forEach(sel => {
        document.querySelectorAll(sel).forEach(
          (el: Element) => el.remove()
        );
      });

      // Try to get main content first
      const mainSelectors = [
        'main', 'article', '[role="main"]',
        '.content', '.article-body',
        '.post-content', '#content', '.main-content',
      ];

      for (const sel of mainSelectors) {
        const el = document.querySelector(sel);
        if (el && (el as HTMLElement).innerText.length > 200) {
          return (el as HTMLElement).innerText;
        }
      }

      return (document.body as HTMLElement).innerText;
    });

    return cleanText(text);

  } finally {
    await page.close();
  }
}

/**
 * Take a screenshot and return path + description.
 */
export async function takeScreenshot(
  url: string,
  description?: string
): Promise<{ filepath: string; summary: string }> {
  const b = await getBrowser();
  const page = await b.newPage();

  try {
    await page.setViewport({ width: 1280, height: 900 });
    await page.goto(url, {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });

    ensureOutputDir();
    const timestamp = Date.now();
    const domain = extractDomain(url);
    const filename = `${domain}_${timestamp}.png`;
    const filepath = path.join(OUTPUT_DIR, filename);

    await page.screenshot({ path: filepath, fullPage: false });

    const title: string = await page.title();
    const summary = description ||
      `Screenshot of ${title} at ${url}`;

    return { filepath, summary };

  } finally {
    await page.close();
  }
}

/**
 * Extract structured data from a page.
 * Returns text + any tables found.
 */
export async function extractStructured(
  url: string
): Promise<{ text: string; tables: string[][] }> {
  const b = await getBrowser();
  const page = await b.newPage();

  try {
    await page.goto(url, {
      waitUntil: 'networkidle2',
      timeout: 30000,
    });

    const data = await page.evaluate(() => {
      // Extract tables
      const tables: string[][] = [];
      document.querySelectorAll('table').forEach(
        (table: Element) => {
          const rows: string[] = [];
          table.querySelectorAll('tr').forEach(
            (row: Element) => {
              const cells = Array.from(
                row.querySelectorAll('td, th')
              ).map((cell: Element) =>
                (cell as HTMLElement).innerText.trim()
              );
              if (cells.length > 0) {
                rows.push(cells.join(' | '));
              }
            }
          );
          if (rows.length > 0) tables.push(rows);
        }
      );

      // Clean noise
      ['script','style','nav','footer'].forEach(tag => {
        document.querySelectorAll(tag).forEach(
          (el: Element) => el.remove()
        );
      });

      return {
        text: (document.body as HTMLElement).innerText,
        tables,
      };
    });

    return {
      text: cleanText(data.text),
      tables: data.tables,
    };

  } finally {
    await page.close();
  }
}

/**
 * Save extracted content to output directory.
 * Returns filepath of saved file.
 */
export function saveContent(
  content: string,
  sourceUrl: string,
  prefix = 'extract'
): string {
  ensureOutputDir();
  const timestamp = new Date()
    .toISOString()
    .replace(/[:.]/g, '-')
    .slice(0, 19);
  const domain = extractDomain(sourceUrl);
  const filename = `${prefix}_${domain}_${timestamp}.txt`;
  const filepath = path.join(OUTPUT_DIR, filename);

  const header = [
    `Source:    ${sourceUrl}`,
    `Extracted: ${new Date().toISOString()}`,
    `Machine:   M2 (azmatsaif)`,
    '─'.repeat(60),
    '',
  ].join('\n');

  fs.writeFileSync(filepath, header + content, 'utf-8');
  return filepath;
}

// ── Helpers ──────────────────────────────────

function cleanText(raw: string): string {
  return raw
    .split('\n')
    .map((l: string) => l.trim())
    .filter((l: string) => l.length > 1)
    .filter((l: string) => !/^[\s\W]{1,3}$/.test(l))
    .join('\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

function extractDomain(url: string): string {
  try {
    return new URL(url).hostname.replace('www.', '');
  } catch {
    return 'unknown';
  }
}

function ensureOutputDir(): void {
  if (!fs.existsSync(OUTPUT_DIR)) {
    fs.mkdirSync(OUTPUT_DIR, { recursive: true });
  }
}
