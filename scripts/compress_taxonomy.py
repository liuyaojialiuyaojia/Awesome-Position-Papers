"""Apply the legacy topic mapping in data/taxonomy.yaml to curated stances."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import common as C  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--curated", default=os.path.join(C.DATA, "curated", "stances.jsonl"))
    args = ap.parse_args()

    tax = C.load_taxonomy()
    mapping = tax.get("legacy_topic_map") or {}
    overrides = tax.get("paper_topic_overrides") or {}
    labels = {spec["label"] for spec in tax["topics"].values()}
    if not 8 <= len(labels) <= 10:
        raise ValueError(f"compressed taxonomy must have 8-10 topics, found {len(labels)}")
    unknown = (set(mapping.values()) | set(overrides.values())) - labels
    if unknown:
        raise ValueError(f"mapping targets missing from topics: {sorted(unknown)}")

    with open(args.curated, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    before = Counter(row["topic"] for row in rows)
    split_decisions = []
    changed = 0
    for row in rows:
        old = row["topic"]
        if old in labels:
            new = old
        else:
            if old not in mapping:
                raise ValueError(f"no topic mapping for {row['id']}: {old}")
            new = mapping[old]
            if old == "Other & cross-cutting":
                new = overrides.get(row["id"], new)
                split_decisions.append((row["id"], new))
        if new != old:
            row["topic"] = new
            changed += 1
    after = Counter(row["topic"] for row in rows)

    temp = args.curated + ".tmp"
    with open(temp, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(temp, args.curated)

    print(f"updated {changed} of {len(rows)} curated rows; {len(before)} topics -> {len(after)}")
    for topic, count in after.most_common():
        print(f"{count:4d}  {topic}")
    if split_decisions:
        print("split decisions from curated stance lines:")
        for paper_id, topic in split_decisions:
            print(f"  {paper_id} -> {topic}")


if __name__ == "__main__":
    main()
