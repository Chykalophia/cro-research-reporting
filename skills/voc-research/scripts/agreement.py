#!/usr/bin/env python3
"""Agreement between AI coding and human coding of customer feedback.

Before trusting AI-coded reviews, survey answers or tickets at scale, have a
human code a random sample (50-100 items) and compare. Cohen's kappa >= 0.7
is the bar used here; published GPT-4o zero-shot coding of survey open-ends
reached ~0.76 (von der Heyde et al., 2025).

Input: a CSV with an id column and one column per coder, e.g.
  id,human,ai
  r1,shipping_cost,shipping_cost
  r2,fit_uncertainty,quality_doubt
Multi-label codes can be separated with ';' (each label is scored as its own
yes/no decision across all items).

  python3 agreement.py coded_sample.csv --a human --b ai
"""
import argparse
import csv
from collections import Counter


def kappa(a, b):
    n = len(a)
    if n == 0:
        return float("nan"), float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb.get(k, 0) for k in ca) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0, po


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv")
    ap.add_argument("--a", default="human")
    ap.add_argument("--b", default="ai")
    ap.add_argument("--sep", default=";")
    ap.add_argument("--min-kappa", type=float, default=0.7)
    args = ap.parse_args(argv)
    with open(args.csv, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows or args.a not in rows[0] or args.b not in rows[0]:
        ap.error(f"CSV needs at least one row and columns '{args.a}' and '{args.b}'")
    a = [(r[args.a] or "").strip() for r in rows]
    b = [(r[args.b] or "").strip() for r in rows]
    if any(not x for x in a + b):
        ap.error("empty coding cells found; code every item, using an explicit 'none' code where needed")
    multi = any(args.sep in x for x in a + b)
    print(f"## Coding agreement ({len(rows)} items, {args.a} vs {args.b})")
    weak = []
    if not multi:
        k, po = kappa(a, b)
        print(f"- Overall: kappa {k:.2f}, raw agreement {po:.0%}")
        labels = sorted(set(a) | set(b))
    else:
        labels = sorted({l for x in a + b for l in x.split(args.sep) if l})
    print("\n| code | human count | AI count | kappa (yes/no) |")
    print("|---|---|---|---|")
    for lab in labels:
        ya = [lab in x.split(args.sep) for x in a]
        yb = [lab in x.split(args.sep) for x in b]
        k, _ = kappa(ya, yb)
        if k < args.min_kappa:
            weak.append(lab)
        print(f"| {lab} | {sum(ya)} | {sum(yb)} | {k:.2f} |")
    if weak:
        print(f"\nBelow {args.min_kappa}: {', '.join(weak)}. Tighten those code definitions, add examples "
              "to the codebook, or merge codes, then re-run on a fresh sample. Watch 'other' codes: "
              "models handle them worst.")
    else:
        print(f"\nAll codes at or above {args.min_kappa}. AI coding can be used for the full set; "
              "spot-check 20 items per new batch.")


if __name__ == "__main__":
    main()
