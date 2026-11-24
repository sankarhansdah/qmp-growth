# Agent 08 — Site design pass (run on demand)

Read `CLAUDE.md` and `.agents/product-marketing.md` first.

## Skills to use
copywriting (landing page copy), site-architecture (nav, hubs), schema (keep JSON-LD intact).
CLAUDE.md rules win over any skill.

## Goal
Give `site/` a distinctive, premium, fast design using the **21st.dev MCP** (`mcp__21st__*` tools)
as the component source, while keeping the site static and SEO-perfect.

## How to use 21st
1. For each section, first ask the inspiration tool for 2–3 options, pick the cleanest one that
   fits a trustworthy business tool (think Linear/Stripe, not a crypto landing page).
2. Generate with the builder tool. Output is React + Tailwind (shadcn style).
3. **Convert to `.astro` components with Tailwind classes** — no React runtime on the page.
   Only make something an island (`client:visible`) if it truly needs JS (e.g. a calculator).
4. Use the refiner tool for polish passes. Use logo search only for third-party brand marks that
   are factually needed (e.g. the official Google Play badge) — never fake customer logos.

## What to build / restyle
- Global: Tailwind (v4 via the Vite plugin), design tokens in one place:
  brand emerald `#0B7A5C`, neutral greys, one sans-serif (system stack or one self-hosted
  variable font, `font-display: swap`), 4/8px spacing, dark mode via `prefers-color-scheme`.
- Header/nav (market switcher: US · UK · CA · AU · IN · AE), footer.
- Landing `/`: hero (value prop + Play badge/waitlist CTA + phone mockup placeholder), how it works
  (3 steps), features grid (only features in `data/product-facts.md`), per-country tax section,
  pricing (free 5 docs/month; paid = "coming soon" until product-facts has prices), FAQ, final CTA.
- Market hub pages, article layout (readable 68–72ch column, table styles, callouts, TOC on
  desktop, sticky-free mobile), `/tools/` index card grid.
- `<AppCta>` restyled; keep its single-CTA rule and UTM links.

## Hard rules
- No invented testimonials, ratings, download counts, customer logos, press mentions or stats.
- Keep every existing URL, canonical, hreflang, sitemap, JSON-LD and content collection schema.
- Accessibility: contrast AA, focus states, alt text, semantic headings, reduced-motion respected.
- Performance budget: Lighthouse mobile ≥ 95 Performance/Accessibility/SEO; no layout shift;
  total JS on article pages ≈ 0 KB.
- `npm run build`, `npm run check`, `node scripts/check-links.mjs` must pass.

## Ship
Commit on your branch, push, open PR `Design: 21st.dev component pass`. In the PR body list which
21st components were used for which section, before/after notes, and any Lighthouse numbers you
could measure (`npx lighthouse` against `npm run preview` if available; otherwise say so).
