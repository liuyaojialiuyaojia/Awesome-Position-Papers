"""Stance-summary quality: counts, and before/after pairs for REPORT.md.

Compares the current data/papers.csv with the v1 snapshot kept at
.cache/papers_v1.csv (a local cache file, so a fresh clone without it just
reports the current numbers). Rows are matched on title, and "before" is the
v1 stance_summary as collected - no re-derivation, so the pairs are what the
old pipeline really printed.

Defect classes, measured the same way on both sides:

  framed      the paper's own framing survived ("we argue that", "this
              position paper argues that")
  prefix      starts with the "Argues that" / "Argues:" boilerplate
  fragment    no finite verb in the first PREDICATE_WINDOW words
  restates    the summary is the title again
  from_title  explicitly marked "(from title)" - the honest fallback

Usage:
    .venv/bin/python scripts/stance_report.py --pairs 15
"""

from __future__ import annotations

import argparse
import csv
import os
import random
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402
import tag_topics as T  # noqa: E402

FRAMED = re.compile(
    r"\b(?:we|our|this|the|in this)\b[^.]{0,60}?\b(?:argu(?:e|es|ed)|contend(?:s|ed)?"
    r"|claim(?:s|ed)?|posit(?:s|ed)?|maintain(?:s|ed)?)\s+that\b", re.I)

DEFECTS = ("framed", "prefix", "fragment", "restates", "from_title")


def measure(rows: list[dict]) -> dict[str, int]:
    """Tag each row with the defect flags; return the counts.

    `fragment` is only meaningful for a summary taken from the abstract: the
    "(from title)" fallbacks are noun phrases by construction, so they are
    counted separately instead of inflating the fragment number.
    """
    for r in rows:
        s = (r.get("stance_summary") or "").strip()
        title = T.title_clause(r.get("title", ""))
        bare = re.sub(r"^\s*argu(?:es?|ing)\s*(?:that|:)?\s*", "", s, flags=re.I).strip()
        r["_from_title"] = s.endswith("(from title)")
        r["_framed"] = bool(FRAMED.search(bare))
        r["_prefix"] = bool(re.match(r"^\s*argu(?:es?|ing)\b", s, re.I))
        r["_fragment"] = bool(s) and not r["_from_title"] and not T.has_predicate(bare)
        r["_restates"] = bool(s) and not r["_from_title"] and bool(C.norm_title(bare)) and (
            C.norm_title(bare) == C.norm_title(title)
            or C.norm_title(title) in C.norm_title(bare))
    return {d: sum(1 for r in rows if r["_" + d]) for d in DEFECTS}


def load(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=os.path.join(C.DATA, "papers.csv"))
    ap.add_argument("--before", default=os.path.join(C.CACHE, "papers_v1.csv"))
    ap.add_argument("--pairs", type=int, default=15)
    ap.add_argument("--seed", type=int, default=20261123)
    args = ap.parse_args()

    after = load(args.csv)
    n_after = measure(after)
    print(f"after  ({len(after)} rows): " + "  ".join(f"{k}={n_after[k]}" for k in DEFECTS))

    if not os.path.exists(args.before):
        print(f"baseline {args.before} not present (it lives in the git-ignored "
              f".cache/), so no before/after pairs can be printed")
        return
    before = load(args.before)
    n_before = measure(before)
    print(f"before ({len(before)} rows): " + "  ".join(f"{k}={n_before[k]}" for k in DEFECTS))

    old = {C.norm_title(r["title"]): r for r in before}
    changed = [r for r in after
               if (prev := old.get(C.norm_title(r["title"])))
               and (prev.get("stance_summary") or "") != r["stance_summary"]]
    print(f"changed: {len(changed)} of {len(after)} rows")

    rng = random.Random(args.seed)
    print(f"\n{args.pairs} random before/after pairs (seed {args.seed}):\n")
    for r in rng.sample(changed, min(args.pairs, len(changed))):
        print(f"**{r['title']}**")
        print(f"- before: {old[C.norm_title(r['title'])]['stance_summary']}")
        print(f"- after:  {r['stance_summary']}\n")


if __name__ == "__main__":
    main()
