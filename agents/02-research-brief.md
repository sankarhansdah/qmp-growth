# Agent 02 — Research brief (per article)

Read `CLAUDE.md`, `templates/brief.md`, `data/sources-allowlist.md`, `data/product-facts.md`.

## Skills to use
Read `.agents/product-marketing.md`, then load these skills: customer-research (mining Reddit/reviews for exact language), competitor-profiling, ai-seo (what makes a page get cited in AI answers).
CLAUDE.md rules win over any skill.

Input: a keyword row id from `data/keywords.csv` (argument), or pick the highest-score
`backlog` row if none given. Mode `refresh` if the id has status `published`.

You produce research only — **no article prose**.

## Steps

1. **Understand intent.** Search the primary keyword in the target market. Read the top 10
   results fully (WebFetch). For each: format, what it covers, what it misses, anything wrong
   or outdated (compare to primary sources), word count estimate.
2. **Collect real questions.** People Also Ask, related searches, and real threads:
   Reddit (r/smallbusiness, r/Contractor, r/freelance, r/electricians, r/HVAC, r/IndiaTax,
   r/UKPersonalFinance, r/AusFinance, r/smallbusinessuk), Quora, Stack Exchange.
   Quote the user's exact wording (short), with URL.
   Reddit and Google's PAA box are often unreachable from WebSearch/WebFetch. Do not stop there.
   Fallbacks, in order, until you have **at least 5 real questions**:
   a) WebSearch question-form queries: `how to <keyword>`, `do I need <keyword>`, `what should
      a <keyword> include`, `<keyword> vs ...` — use questions shown in result titles/snippets;
   b) `site:reddit.com <keyword>` in WebSearch — thread titles in results count, even if the
      page itself won't load;
   c) trade and business forums (forums.mikeholt.com, contractortalk.com,
      ukbusinessforums.co.uk, whirlpool.net.au, Stack Exchange), Quora result titles;
   d) the questions (never the answers) in competitors' FAQ sections.
   Record each question with its URL. The writer needs these for the FAQ; an empty FAQ is a
   failed brief.
3. **Pain from reviews.** 1–3★ Play Store reviews of competitors in `data/competitors.md`
   that relate to this topic. Exact words + link.
4. **Facts from primary sources only.** Every rule, rate, threshold, required field, deadline:
   claim + exact source URL + the sentence that proves it + date accessed.
   Use only domains in `data/sources-allowlist.md` for facts. If unsure, mark `UNVERIFIED`
   and the writer will exclude it.
5. **Gap & angle.** What will make our page clearly the best answer: worked example numbers,
   downloadable template, calculator, checklist, trade-specific detail.
6. **Outline.** H2/H3 skeleton, each section listing which facts/questions it answers.
7. **Internal links.** From `data/link-map.json`: which existing pages this should link to and
   which should link back.
8. Save `briefs/<market>/<slug>.md`, set the keyword row `status=briefed`.

Commit to the run's branch (the pipeline continues on the same branch; do not open a PR
unless run standalone).
