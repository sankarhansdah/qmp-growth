# Bootstrap report — 2026-11-24

## Status: scaffold written, NOT built or verified

The sandbox denied every `npm` command (`npm view`, and by extension `npm install`,
`npm run build`, `npm run check`). So **`npm run build` and `npm run check` have not been run.**
The code may contain errors that only a build will show. Please run
`cd site && npm install && npm run build && npm run check && npm run check-links` before merging.

## What was added
- `site/` Astro project: `astro.config.mjs` (site = https://quotationmaker.pro, `@astrojs/sitemap`),
  `package.json`, `tsconfig.json`, `.gitignore`.
- Content collection `articles` (`site/src/content.config.ts`) with the requested schema.
- Routes: `/` landing page, `/[market]/` hubs (us, uk, ca, au, in, ae) grouped by cluster,
  `/[market]/[slug]/` articles, `/tools/` with a small plain-JS example calculator.
- Article pages emit canonical, hreflang alternates (+ x-default) for a shared `hreflangGroup`,
  Open Graph, Article / FAQPage / BreadcrumbList JSON-LD. `public/robots.txt` points to the sitemap.
- `<AppCta>` component (single CTA per article).
- `scripts/check-links.mjs`: scans built HTML for broken internal links (`npm run check-links`).

## Decisions / deviations
- Added a `cluster` field (default "General") to the schema so hubs can group by topic cluster.
- Dependency versions are ranges (`astro ^5`, `@astrojs/sitemap ^3.2`, `@astrojs/check ^0.9`)
  chosen from memory, not verified against the registry. The spec asks for latest stable; bump if needed.
- `data/product-facts.md` has `<PACKAGE_ID>` unfilled, so `AppCta` shows the "coming soon" waitlist
  variant with no Play link. Once the ID is set in `site/src/lib/product.ts`, the Play badge link with
  UTM params switches on. There is no real Play badge image yet.
- Global-market articles (no path prefix) have no route yet; `/[market]/[slug]/` would collide with
  the `/[market]/` hubs. Needs a decision when the first global article exists.
- The landing page uses only facts from `product-facts.md`. Paid plan details are marked "to be announced".
  No testimonials or download counts. Screenshots are a placeholder.
- Lighthouse 95+ not measured.

## Open questions for Sankar
1. Play package ID, and the paid plan names/prices.
2. Waitlist: where should the "coming soon" CTA point (form URL)?
3. How should global (`/`) articles be routed?
