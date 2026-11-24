# Fact-check: us/electrical-estimate-template (2026-11-24)

| Claim | Source | Verdict | Note |
|---|---|---|---|
| NY: all charges for materials and labor billed for repair, maintenance or installation are taxable, incl. expenses and markups | tax.ny.gov repair_maintenance (fetched today) | PASS | Quote matches. |
| NY "that case" implied a panel job is taxable | same page | FIXED | Bulletin also says capital improvements are not taxable and some work needs case-by-case review. Caveat added to the article. |
| TX lump-sum: contractor pays tax on supplies/materials/equipment when buying | comptroller.texas.gov 94-116 (fetched today) | PASS | Matches. |
| TX separated: resale certificates instead of paying tax on materials | same | PASS | Matches. |
| "Tax shows up as a line on the customer's estimate" under separated contracts | same | PASS | Page says contractor charges customer sales tax on materials. |
| Texas publication dated March 2007 | same | PASS | Article already warns the reader to check for current guidance. |
| Allowlist | tax.ny.gov, comptroller.texas.gov | PASS | Both on the us list. |
| Worked example arithmetic | recomputed | PASS | 573.00; markup 114.60; 687.60; +850 = 1,537.60; tax 123.008 -> 123.01, total 1,660.61; 55.008 -> 55.01, total 1,592.61; deposit 415.15 (415.1525); balance 1,245.46. |
| CSV formulas | checked cell refs rows 10-26 | PASS | Refs are consistent. |
| Estimate/quote/bid definitions, 30-day validity, 25% deposit | none | PASS | Labelled as common usage or illustrative, not as rules or law. |
| Invented stats, testimonials, quotes | n/a | PASS | None found. |
| Product claims | product-facts.md | PASS | Only the waitlist CTA component and the footer; no feature claims in the body. |

## Remaining issues (not FAILs)
- Quality bar 4 is not met: the FAQ is empty because no real People Also Ask or Reddit questions were collected. Add them before shipping.
- Three SANKAR markers are open, and `data/experience-notes.md` is empty.
- CTA is the waitlist variant because the app is unpublished.
- Texas source is from 2007, so it needs re-verification against current Comptroller guidance.

Unfixable FAILs: 0, so `published` is unchanged.
`reviewBy` stays 2027-05-24 (6 months, the maximum).
