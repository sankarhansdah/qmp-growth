# Agent 05 — Editor + internal linker

Read `CLAUDE.md`, the article, `data/link-map.json`, the fact-check report.

## Edit
- Cut filler, repetition, hedging. Keep every cited fact intact (do not change numbers).
- Check voice rules and banned phrases. Check market spelling.
- Headings: descriptive, contain natural variations of secondary keywords. No keyword stuffing.
- Title ≤ 60 chars, description ≤ 155 chars.

## Link
- This article → 1 hub page for its market + 2–4 genuinely related articles/tools (descriptive
  anchor text, not "click here", no exact-match anchor spam).
- 2–4 existing related articles → add a contextual link to this article (edit those files in
  the same PR).
- If a `hreflangGroup` equivalent exists in another market, set the same group.
- Update `data/link-map.json`: `{ "<market>/<slug>": { "cluster": "...", "links_out": [], "links_in": [] } }`.
- Never link to a page that doesn't exist. Run `node scripts/check-links.mjs` in `site/`.

## Ship
- `npm run build` in `site/` must pass.
- Set keyword row `status=published`, `published: true` (unless fact-check set it false).
- Push branch, open the PR: title `Article: <title> (<market>)`. Body: target keyword + volume,
  what makes it better than the current top results, sources, fact-check summary, and a
  checklist of `<!-- SANKAR -->` markers for him to fill.
