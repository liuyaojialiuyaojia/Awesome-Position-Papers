"""List public papers that have no curated stance yet.

Writes data/needs_curation.csv (id, title, venue, year, url, abstract) so a
reviewer or model can write their rows in data/curated/stances.jsonl.
"""

from __future__ import annotations

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C  # noqa: E402


def main() -> None:
    curated_path = os.path.join(C.DATA, "curated", "stances.jsonl")
    curated = set()
    if os.path.exists(curated_path):
        with open(curated_path, encoding="utf-8") as f:
            curated = {json.loads(line)["id"] for line in f if line.strip()}
    with open(os.path.join(C.DATA, "papers.csv"), encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f)
                if r["id"] not in curated and r.get("excluded", "false") != "true"]
    cols = ["id", "title", "venue", "year", "url", "abstract"]
    out = os.path.join(C.DATA, "needs_curation.csv")
    if not rows:  # nothing to do: no file, so the repo only shows it when it matters
        if os.path.exists(out):
            os.remove(out)
        print("needs curation: 0 papers")
        return
    with open(out, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"needs curation: {len(rows)} papers -> data/needs_curation.csv")


if __name__ == "__main__":
    main()
