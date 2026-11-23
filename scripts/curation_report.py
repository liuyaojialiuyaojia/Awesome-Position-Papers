"""Print the reproducible v3 confidence, topic, and stance comparison report."""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402


def read_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=os.path.join(C.DATA, "papers.csv"))
    ap.add_argument("--before", default=os.path.join(C.CACHE, "papers_v2.csv"))
    ap.add_argument("--curated", default=os.path.join(C.DATA, "curated", "stances.jsonl"))
    ap.add_argument("--pairs", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20261123)
    args = ap.parse_args()

    after = read_csv(args.csv)
    before = read_csv(args.before)
    with open(args.curated, encoding="utf-8") as fh:
        curated = [json.loads(line) for line in fh if line.strip()]

    old_by_id = {row["id"]: row for row in before}
    if set(old_by_id) != {row["id"] for row in after}:
        raise ValueError("before/after paper ids differ; cannot produce a like-for-like report")
    if {row["id"] for row in curated} != {row["id"] for row in after}:
        raise ValueError("curated ids do not exactly cover the rebuilt dataset")

    confidence = Counter(row["confidence"] for row in curated)
    old_topics = Counter(row["topic"] for row in before)
    new_topics = Counter(row["topic"] for row in after)

    print("## v3 changes\n")
    print(f"Read all **{len(after)} abstracts** and wrote one curated stance, topic, and confidence "
          "value per paper in `data/curated/stances.jsonl`, in resumable batches of 25. "
          "Kimi-K3.1-Pro (via Qoder CLI) wrote the drafts directly; no external LLM API or "
          "keyword generator was used. The build now applies these rows by stable paper id, "
          "while future uncurated papers retain automatic drafts.\n")
    print("### Confidence\n")
    print("| Confidence | Papers |")
    print("|---|---:|")
    for level in ("high", "medium", "low"):
        print(f"| {level} | {confidence[level]} |")
    print(f"| **Total** | **{len(curated)}** |\n")

    print("### Topic distribution\n")
    print("Before is `.cache/papers_v2.csv`; after is the rebuilt `data/papers.csv`.\n")
    print("| Topic | Before | After | Change |")
    print("|---|---:|---:|---:|")
    topics = sorted(set(old_topics) | set(new_topics), key=lambda topic: (-new_topics[topic], topic))
    for topic in topics:
        delta = new_topics[topic] - old_topics[topic]
        print(f"| {topic} | {old_topics[topic]} | {new_topics[topic]} | {delta:+d} |")
    print(f"| **Total** | **{len(before)}** | **{len(after)}** | **{len(after) - len(before):+d}** |\n")

    print(f"### {args.pairs} random stance revisions\n")
    print(f"Deterministic sample from all {len(after)} papers, seed `{args.seed}`.\n")
    for index, row in enumerate(random.Random(args.seed).sample(after, args.pairs), 1):
        old = old_by_id[row["id"]]
        print(f"{index}. **{row['title']}** (`{row['id']}`)")
        print(f"   - Old: {old['stance_summary']}")
        print(f"   - New: {row['stance_summary']}\n")


if __name__ == "__main__":
    main()
