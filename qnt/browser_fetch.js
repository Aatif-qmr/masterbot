#!/usr/bin/env node
/**
 * QNT Browser Fetch — called by M1 via SSH
 * Usage: node browser_fetch.js <command> [url]
 * Commands: feargreed | coinglass | arxiv | page <url>
 */

async function main() {
  const command = process.argv[2];
  const url = process.argv[3];

  // Dynamic import of compiled extractors (ESM)
  let extractors;
  try {
    extractors = await import(
      '/Users/azmatsaif/cipher/qnt/src/packages/core/dist/src/qnt/extractors.js'
    );
  } catch(e) {
    console.error('Extractors not compiled or error loading. Run: npm run build');
    console.error(e);
    process.exit(1);
  }

  try {
    let result = '';
    switch(command) {
      case 'feargreed':
        result = await extractors.extractFearGreed();
        break;
      case 'coinglass':
        result = await extractors.extractCoinGlass();
        break;
      case 'arxiv':
        result = await extractors.extractArxivRecent(url || 'q-fin.TR');
        break;
      case 'page':
        if (!url) { console.error('URL required'); process.exit(1); }
        result = await extractors.extractAnyPage(url);
        break;
      default:
        console.error(`Unknown command: ${command}`);
        console.error('Usage: node browser_fetch.js <feargreed|coinglass|arxiv|page> [url]');
        process.exit(1);
    }
    console.log(result);
  } catch(e) {
    console.error(`Browser fetch error: ${e}`);
    process.exit(1);
  }
}

main().catch(console.error);
