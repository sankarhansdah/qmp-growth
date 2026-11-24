# Agent 00 — Bootstrap the website (run once)

Read `CLAUDE.md` first.

## Skills to use
Read `.agents/product-marketing.md`, then load these skills: site-architecture (page hierarchy, URL structure, nav), schema (JSON-LD), seo-audit (technical checklist), copywriting (landing page `/`).
CLAUDE.md rules win over any skill.

Create an Astro static site in `site/`:

1. Astro (latest stable) + content collections. Collection `articles` with schema:
   `title, description, market (us|gb|ca|au|in|ae|global), slug, primaryKeyword,
   secondaryKeywords[], intent (informational|template|tool|comparison), published, updated,
   lastReviewed, reviewBy?, faq[{q,a}], sources[{title,url}], hreflangGroup?`
2. Routes: `/` (global), `/us/`, `/uk/`, `/ca/`, `/au/`, `/in/`, `/ae/` hub pages that list
   that market's articles grouped by topic cluster, plus `/[market]/[slug]/` article pages.
3. Every article page emits: canonical, `hreflang` alternates for every page sharing a
   `hreflangGroup` (plus `x-default`), Open Graph tags, `Article` + `FAQPage` JSON-LD,
   breadcrumb JSON-LD, sitemap via `@astrojs/sitemap`, `robots.txt`.
4. `/tools/` section for interactive tools (plain JS islands, no framework required).
5. Layout: fast, minimal, readable (max-width ~70ch, system font stack, no cookie wall,
   Lighthouse 95+). One CTA component `<AppCta market=...>` with a Google Play badge link
   using `data/product-facts.md` → Play URL with UTM `?utm_source=site&utm_medium=cta&utm_campaign=<slug>`.
6. `npm run build` and `npm run check` must pass. Add `scripts/check-links.mjs` that fails on
   broken internal links.
7. Landing page `/` : clear value prop, screenshots placeholder, features, pricing (free 5/month),
   FAQ, Play badge. No invented testimonials or download counts.

Open a PR. Report in `reports/<date>-bootstrap.md`.
