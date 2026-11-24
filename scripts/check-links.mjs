#!/usr/bin/env node
// Fails on broken internal links in a built site. Usage: node scripts/check-links.mjs [distDir]
import { readdirSync, readFileSync, existsSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';

const dist = resolve(process.argv[2] ?? 'site/dist');
if (!existsSync(dist)) { console.error(`dist not found: ${dist} (run npm run build first)`); process.exit(2); }

const walk = (d) => readdirSync(d).flatMap((f) => {
  const p = join(d, f);
  return statSync(p).isDirectory() ? walk(p) : [p];
});

const exists = (urlPath) => {
  const clean = decodeURIComponent(urlPath.split('#')[0].split('?')[0]);
  const p = join(dist, clean);
  if (existsSync(p) && statSync(p).isFile()) return true;
  return existsSync(join(p, 'index.html'));
};

const bad = [];
for (const file of walk(dist).filter((f) => f.endsWith('.html'))) {
  const html = readFileSync(file, 'utf8');
  for (const m of html.matchAll(/<(?:a|link)\b[^>]*?\bhref=["']([^"']+)["']/g)) {
    let href = m[1];
    if (/^(mailto:|tel:|javascript:|#)/.test(href)) continue;
    if (href.startsWith('https://quotationmaker.pro')) href = href.slice('https://quotationmaker.pro'.length) || '/';
    if (!href.startsWith('/') || href.startsWith('//')) continue; // external
    if (!exists(href)) bad.push(`${file.replace(dist, '')} -> ${href}`);
  }
}
if (bad.length) { console.error(`Broken internal links:\n${bad.join('\n')}`); process.exit(1); }
console.log('All internal links OK');
