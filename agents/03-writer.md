# Agent 03 — Writer

Read `CLAUDE.md`, the brief `briefs/<market>/<slug>.md`, `data/product-facts.md`,
`data/experience-notes.md`, `templates/article.md`.

Write `site/src/content/articles/<market>/<slug>.md` **only from the brief**. Do not add facts
that are not in the brief's verified facts table. Skip anything marked `UNVERIFIED`.

## Structure

1. Title (≤ 60 chars, contains primary keyword naturally) + meta description (≤ 155 chars,
   states the concrete payoff).
2. **Answer in the first 100 words.** The reader should get the core answer immediately.
3. Main sections from the brief's outline. Each section opens with the direct answer.
4. **At least one worked example** with real numbers in the market's currency and format
   (e.g. a US electrician's estimate with labor, materials, sales tax line; an India quotation
   with CGST+SGST vs IGST split). Show the arithmetic.
5. The asset promised in the brief (template table, checklist, or link to a `/tools/` page).
   If it's a downloadable template, also create it in `site/public/templates/<market>/`
   (Markdown/CSV/HTML-printable; PDFs later).
6. FAQ: 4–8 real questions from the brief, short direct answers, in frontmatter `faq`.
7. One `<AppCta>` after the value is delivered (see CLAUDE.md conversion rules).
8. Sources section listing every primary source used, plus `Last reviewed: <date>`.
9. Inline citation for every factual claim as a markdown link to the source.

## Rules
- Market spelling, currency, date format, terminology (see CLAUDE.md table).
- Target length = whatever fully answers it; usually 1,200–2,500 words. No padding.
- Trade pages: insert `<!-- SANKAR: ... -->` markers where first-hand detail would help.
- Set keyword row `status=drafted`, `target_url`.
