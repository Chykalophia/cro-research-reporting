# Audit fixture: expected checklist results

`pdp.html` is a deliberately flawed product page. Render it and score the PDP checklist:

```bash
python3 skills/ecommerce-cro-audit/scripts/capture_pages.py file://$PWD/evals/audit-fixture/pdp.html --out /tmp/fixture-captures --no-proxy
```

Then ask the `cro-auditor` agent (or the skill) to score `references/heuristic-checklist.md` from those captures, with no funnel data. Compare against this key. Track **precision** (No answers that are correct) and **recall** (seeded failures caught) across model versions; Baymard's test of GPT-4 found ~20% precision on open-ended audits, so precision is the number to watch.

| ID | Expected | Why |
|---|---|---|
| P1 | No | H1 is "Strata ^ Runner ~ *": no product type or benefit |
| P2 | Yes | Price visible near the title on mobile |
| P3 | No | ATC sits below the description and tabs; not above the fold on mobile, no sticky bar |
| P4 | No | ATC is grey-on-grey, the least prominent control |
| P5 | No | One placeholder image, no in-scale shot |
| P6 | Can't tell / No | No zoom behaviour present |
| P7 | Can't tell | Single image, no variants with media |
| P9 | No | No rating near the title |
| P10 | No | No reviews at all |
| P11 | No | No size guide link at the selector, EU sizes only |
| P12 | No | Sold-out sizes offer no back-in-stock capture |
| P13 | No | No shipping cost or threshold anywhere |
| P14 | No | Returns tab exists but is empty |
| P15 | No | All three tabs are empty |
| P16 | No | Description is four paragraphs of story, no bullets |
| P17 | Yes | No horizontal scroll |

Also expected:
- Every item above lands in **Investigate** or **Just do it** only with corroboration; with no funnel or VoC data supplied, the auditor should say that most items stay at Low confidence and should ask for data, not promise lifts.
- The "Unverified observations" list may mention the long brand story but must not present it as a finding.
- The auditor must not invent reviews, traffic numbers or benchmark comparisons.
