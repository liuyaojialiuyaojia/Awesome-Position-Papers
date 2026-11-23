"""Flag possible dataset problems for human review; never exclude rows itself."""

from __future__ import annotations

import argparse
import difflib
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402
import link_arxiv  # noqa: E402

PREFIX = re.compile(r"^\s*position(?:\s+paper)?\s*:\s*", re.I)
WITHDRAWN = re.compile(r"\b(?:withdrawn|withdrawal|retracted)\b", re.I)
TITLE_POSITION_CUE = re.compile(
    r"\b(?:should|must|need(?:s)?|require[sd]?|cannot|can't|not|no|beyond|rethink(?:ing)?|"
    r"reconsider|against|stop|avoid|pause|urge[sd]?|essential|unsustainable|pitfalls?|"
    r"barrier|missing|path(?:way)?|call|demand|wrong|weak|fragile|inevitable|key concern|"
    r"challenge[sd]?|opportunit(?:y|ies)|perspective|how|why|what)\b", re.I)
GENERIC_PROPOSAL = re.compile(
    r"\bshould\s+(?:use|integrate|adopt|combine|pursue|consider|recognize|involve|"
    r"treat|move|shift|embrace|expose)\b", re.I)


def words(title: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", PREFIX.sub("", title.lower()))


def near_identical(a: dict, b: dict) -> tuple[float, str] | None:
    if link_arxiv.accepted(a["title"], b["title"]):
        return 1.0, "shared_title_prefix"
    aw, bw = words(a["title"]), words(b["title"])
    if min(len(aw), len(bw)) < 5:
        return None
    aset, bset = set(aw), set(bw)
    jaccard = len(aset & bset) / len(aset | bset)
    ratio = difflib.SequenceMatcher(None, " ".join(aw), " ".join(bw)).ratio()
    if ratio >= 0.90 or (jaccard >= 0.80 and ratio >= 0.82):
        return max(ratio, jaccard), "similar_title"
    return None


def base_arxiv_id(arxiv_id: str) -> str:
    return re.sub(r"v\d+$", "", arxiv_id.strip()).replace("/", "-")


def raw_arxiv_metadata() -> dict[str, dict]:
    path = os.path.join(C.RAW_DIR, "arxiv_position_titles.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        rows = json.load(fh)
    return {base_arxiv_id(row.get("arxiv_id", "")): row for row in rows if row.get("arxiv_id")}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=os.path.join(C.DATA, "papers.csv"))
    ap.add_argument("--out", default=os.path.join(C.DATA, "filter_candidates.jsonl"))
    args = ap.parse_args()

    rows = C.read_csv(args.csv)
    raw = raw_arxiv_metadata()
    flagged: dict[str, dict] = {}

    def flag(row: dict, reason: str, **details) -> None:
        candidate = flagged.setdefault(row["id"], {
            "id": row["id"], "title": row["title"], "venue": row["venue"],
            "reasons": [], "details": {},
        })
        if reason not in candidate["reasons"]:
            candidate["reasons"].append(reason)
        candidate["details"].update(details)

    by_arxiv: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row.get("excluded", "").lower() == "true":
            continue
        aid = base_arxiv_id(row.get("arxiv_id", ""))
        if aid:
            by_arxiv[aid].append(row)
    for aid, group in by_arxiv.items():
        if len(group) < 2:
            continue
        ids = [row["id"] for row in group]
        for row in group:
            flag(row, "duplicate_arxiv_id", arxiv_id=aid, matches=[i for i in ids if i != row["id"]])

    for i, left in enumerate(rows):
        for right in rows[i + 1:]:
            same_arxiv = (left.get("arxiv_id") and
                          base_arxiv_id(left["arxiv_id"]) == base_arxiv_id(right.get("arxiv_id", "")))
            already_reviewed = "true" in {left.get("excluded", "").lower(),
                                          right.get("excluded", "").lower()}
            if same_arxiv and not already_reviewed:
                continue
            match = near_identical(left, right)
            if not match:
                continue
            similarity, method = match
            for row, other in ((left, right), (right, left)):
                flag(row, "near_duplicate_title", match_id=other["id"],
                     match_title=other["title"], similarity=round(similarity, 3), method=method)

    for row in rows:
        abstract = (row.get("abstract") or "").strip()
        if len(abstract) < 400 or len(abstract.split()) < 60:
            flag(row, "short_abstract", abstract_characters=len(abstract),
                 abstract_words=len(abstract.split()))

        raw_row = raw.get(base_arxiv_id(row.get("arxiv_id", "")), {})
        withdrawal_text = " ".join((abstract, raw_row.get("comment", "")))
        match = WITHDRAWN.search(withdrawal_text)
        if match:
            start = max(0, match.start() - 100)
            flag(row, "withdrawal_mention", evidence=withdrawal_text[start:match.end() + 140])

        if row.get("venue") != "arXiv-only":
            continue
        title = PREFIX.sub("", row.get("title", ""))
        stance = row.get("stance_summary", "")
        if not TITLE_POSITION_CUE.search(title) and GENERIC_PROPOSAL.search(stance):
            flag(row, "weak_position_signal")

    candidates = sorted(flagged.values(), key=lambda r: (r["reasons"][0], r["title"].lower()))
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        for candidate in candidates:
            fh.write(json.dumps(candidate, ensure_ascii=False) + "\n")

    counts = {reason: sum(reason in c["reasons"] for c in candidates)
              for reason in ("duplicate_arxiv_id", "near_duplicate_title", "withdrawal_mention",
                             "short_abstract", "weak_position_signal")}
    print(f"flagged {len(candidates)}/{len(rows)} rows -> {os.path.relpath(args.out, C.REPO)}")
    for reason, count in counts.items():
        print(f"  {count:3d}  {reason}")
    print("Review these candidates only; write confirmed exclusions to data/curated/filter.jsonl.")


if __name__ == "__main__":
    main()
