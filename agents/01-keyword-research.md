# Agent 01 — Keyword research (monthly)

Read `CLAUDE.md`, `data/keywords.csv`, `data/competitors.md`.

Goal: keep `data/keywords.csv` a ranked, deduplicated backlog of topics worth writing, per market.

## Steps

1. **Seed** from `data/seeds.md` for each market + any query in Search Console with impressions
   but no page targeting it (find the Search Console query operation with
   `gum search "search console search analytics query"`; last 90 days, dimensions query+page+country).
2. **Expand** with Google Ads Keyword Planner via gum (`gum search "keyword planner generate keyword ideas"`)
   using each market's geo + language. Capture avg monthly searches and competition.
   If Keyword Planner is unavailable (no developer token yet), use Google Trends via gum +
   People Also Ask / related searches from WebSearch, and mark `volume_source=estimate`.
3. **Check the SERP** for the top candidates (WebSearch, the market's country): who ranks, what
   format wins (template, calculator, guide), are big sites dominating with thin pages
   (= opportunity) or strong pages (= skip for now).
4. **Cluster** keywords that one page should answer together. One row per cluster.
5. **Score** each cluster:
   `score = volume_weight * intent_weight * winnability * product_fit`
   - intent: template/tool = 3, how-to = 2, definition = 1
   - winnability: 1–3 from SERP check
   - product_fit: 3 if the reader would naturally need QMP next, 1 if unrelated
6. Write back to `data/keywords.csv` (keep existing rows; update numbers; never delete rows
   with status `published`).

## CSV columns
`id,market,cluster,primary_keyword,secondary_keywords,intent,format,monthly_volume,volume_source,competition,winnability,product_fit,score,status,target_url,notes`
`status` ∈ `backlog | briefed | drafted | published | skip`.

Open a PR with the diff + a report `reports/<date>-keywords.md` listing the top 15 new
opportunities per market and why.
