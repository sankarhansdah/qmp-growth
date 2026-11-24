# Agent 06 — Search Console monitor (weekly)

Read `CLAUDE.md`, `data/keywords.csv`, `data/link-map.json`.

Use `scripts/gsc` for all Search Console data (not gum — gum needs a browser login on this server).
Run `scripts/gsc --help` once. Commands:
- `scripts/gsc query --days 28` (current) and `scripts/gsc query --days 28 --prev` (previous window)
- `scripts/gsc query --days 28 --country usa` (per-market; alpha-3: usa, gbr, can, aus, ind, are)
- `scripts/gsc inspect --url <full page URL>`
- `scripts/gsc sitemaps`
- `scripts/gsc submit-sitemap --url https://quotationmaker.pro/sitemap-index.xml` (only if missing/erroring)
If the site has no data yet (new site), say so in the report and stop — do not invent numbers.

## Steps
1. Pull last 28 days vs previous 28 days, dimensions `page,query,country`.
2. Find:
   - **Striking distance**: queries at avg position 4–20 with ≥ 50 impressions → page needs a
     refresh/expansion targeting that query.
   - **Low CTR**: position ≤ 5 but CTR below 2% → title/description rewrite.
   - **Decliners**: pages losing > 30% clicks.
   - **New queries** with no target page → add to `data/keywords.csv` as `backlog`.
   - **Due reviews**: articles whose `reviewBy` date is past or within 14 days.
3. URL-inspect pages published in the last 14 days; list any not indexed and why.
4. Check sitemap status; report errors.
5. Write `queue/refresh.csv` rows: `market,slug,reason,queries,priority`.
6. Write `reports/<date>-gsc.md` (plain-language summary + top 10 actions).
7. Low-CTR fixes only (title/description edits) may be made directly in this run's PR.
   Content refreshes are done by the pipeline in `refresh` mode, not here.
