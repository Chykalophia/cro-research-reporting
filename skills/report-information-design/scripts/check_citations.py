#!/usr/bin/env python3
"""Mechanical citation check for a report (HTML or Markdown).

LLM research tools invent or break links: deep-research agents produced ~10.7%
hallucinated URLs in one 2026 study, and an automated liveness check plus
correction brought that under 1% (Rao, Wong & Callison-Burch, arXiv 2604.03173).
This script does the mechanical part so the verifier can spend judgement on logic.

It checks:
  1. every cited URL resolves (HTTP status), run in parallel
  2. optional: each load-bearing number/quote appears on its source page
     (--claims CSV with columns: url,expect   e.g.  https://baymard.com/...,70.22)
  3. HTML footnotes: every href="#s-..." has a matching id, numbering is gapless

  python3 check_citations.py report.html
  python3 check_citations.py report.html --claims claims.csv --json
"""
import argparse
import concurrent.futures as cf
import csv
import html as htmlmod
import json
import re
import sys
import urllib.error
import urllib.request

URL_RE = re.compile(r"""https?://[^\s"'<>)\]]+""")
UA = "Mozilla/5.0 (citation-check; +https://github.com/Chykalophia/cro-research-reporting)"


def extract_urls(text):
    urls = []
    for u in URL_RE.findall(text):
        u = htmlmod.unescape(u).rstrip(".,;:")
        if u not in urls and "fonts.googleapis" not in u and "fonts.gstatic" not in u:
            urls.append(u)
    return urls


def fetch(url, timeout=20, want_body=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read(3_000_000).decode("utf-8", "replace") if want_body else ""
            return {"status": r.status, "final_url": r.geturl(), "body": body}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "final_url": url, "body": ""}
    except Exception as e:  # DNS, TLS, timeout
        return {"status": None, "error": f"{type(e).__name__}: {str(e)[:120]}", "final_url": url, "body": ""}


def classify(res):
    s = res.get("status")
    if s is None:
        return "error"
    if 200 <= s < 400:
        return "ok"
    if s in (401, 403, 429, 999):
        return "blocked (check by hand)"
    return "dead"


def visible_text(page):
    page = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", page)
    page = re.sub(r"(?s)<[^>]+>", " ", page)
    return re.sub(r"\s+", " ", htmlmod.unescape(page))


def footnote_integrity(text):
    refs = re.findall(r'href="#(s-[\w-]+)"', text)
    ids = set(re.findall(r'id="(s-[\w-]+)"', text))
    missing = sorted(set(refs) - ids)
    uncited = sorted(ids - set(refs))
    nums = [int(n) for n in re.findall(r'id="s-(\d+)"', text)]
    gaps = sorted(set(range(1, max(nums) + 1)) - set(nums)) if nums else []
    return {"refs_without_entry": missing, "entries_never_cited": uncited, "numbering_gaps": gaps}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("report")
    ap.add_argument("--claims", help="CSV with url,expect columns")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    text = open(args.report, encoding="utf-8").read()
    urls = extract_urls(text)
    claims = []
    if args.claims:
        with open(args.claims, newline="") as f:
            claims = [r for r in csv.DictReader(f) if r.get("url")]
    need_body = {c["url"] for c in claims}
    with cf.ThreadPoolExecutor(args.workers) as ex:
        futs = {u: ex.submit(fetch, u, 20, u in need_body) for u in set(urls) | need_body}
        res = {u: f.result() for u, f in futs.items()}

    links = [{"url": u, "status": res[u].get("status"), "result": classify(res[u]),
              "error": res[u].get("error")} for u in urls]
    claim_rows = []
    for c in claims:
        body = visible_text(res[c["url"]].get("body", ""))
        exp = c["expect"].strip()
        found = exp.lower() in body.lower() if body else None
        claim_rows.append({"url": c["url"], "expect": exp, "found": found})
    foot = footnote_integrity(text) if "<" in text else None
    out = {"links": links, "claims": claim_rows, "footnotes": foot}
    bad = [l for l in links if l["result"] != "ok"]
    failed_claims = [c for c in claim_rows if c["found"] is not True]

    if args.json:
        print(json.dumps(out, indent=2))
    else:
        print(f"## Citation check: {args.report}")
        print(f"- {len(urls)} unique URLs: {len(urls) - len(bad)} ok, {len(bad)} need attention")
        for l in bad:
            print(f"  - {l['result']}: {l['url']} ({l['status'] or l['error']})")
        if claim_rows:
            print(f"- Claims: {len(claim_rows) - len(failed_claims)}/{len(claim_rows)} found on the source page")
            for c in failed_claims:
                state = "page not readable" if c["found"] is None else "NOT FOUND"
                print(f"  - {state}: '{c['expect']}' at {c['url']}")
        if foot:
            issues = {k: v for k, v in foot.items() if v}
            print(f"- Footnotes: {'clean' if not issues else issues}")
        print("\nBlocked pages and 'not found' numbers need a human or WebFetch look: the figure may sit "
              "in a PDF, a table image or behind a paywall. Never keep a figure you could not confirm "
              "without labelling it unverified.")
    sys.exit(1 if [l for l in links if l["result"] == "dead"] or [c for c in claim_rows if c["found"] is False] else 0)


if __name__ == "__main__":
    main()
