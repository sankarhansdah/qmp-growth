# Agent 07 — Play Store listing optimisation (every 6 weeks)

Read `CLAUDE.md`, `data/product-facts.md`, `data/keywords.csv`, `queue/aso.md`,
current `fastlane/metadata/android/<locale>/*`.

Store listing limits: title ≤ 30 chars, short description ≤ 80 chars, full description ≤ 4000.

## Steps
1. For each locale (en-US, en-GB, en-IN; more when added): gather app-store keywords —
   Google Play search suggestions and competitor titles/short descriptions for
   "quote maker", "estimate maker", "invoice maker", "quotation maker", "contractor estimate",
   "GST invoice" (India only). Use WebSearch/WebFetch on play.google.com listings.
2. Pick 1 primary + 3–5 secondary terms per locale. US leans "estimate", IN/GB lean "quotation".
3. Rewrite:
   - `title.txt`: brand + primary term, ≤ 30 chars.
   - `short_description.txt`: concrete benefit + primary term, ≤ 80 chars.
   - `full_description.txt`: first 2 lines carry the value; features as short lines; natural
     use of secondary terms (no keyword lists); free plan stated accurately; no claims beyond
     `data/product-facts.md`; no "best/#1/top" claims (Play policy).
4. Validate lengths with a script; fail if any limit is exceeded.
5. Record the previous version and the hypothesis in `queue/aso.md` with today's date so the
   next run can compare installs/conversion (Sankar pastes Play Console store listing
   conversion numbers there).
6. Do not run more often than every 6 weeks per locale — check `queue/aso.md` dates first;
   if too soon, write a report and stop.
7. Open PR `ASO: <locales> <date>`. Merging it triggers the fastlane upload workflow.

Also list (in the report, not as changes) screenshot caption ideas and a store listing
experiment suggestion Sankar can set up manually in Play Console.
