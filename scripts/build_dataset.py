"""Merge the four collectors into data/papers.csv.

Order of precedence is the order given in AGENTS.md: ICML 2024, ICML 2025,
NeurIPS 2025, arXiv title scan. Deduplication is by normalised title, so a
paper that exists both on arXiv and in a venue track becomes one row that
keeps the venue's metadata and gains the arXiv id.

Two joins happen here:
  * venue rows get an arxiv_id, from the arXiv dump when the title matches and
    otherwise from one targeted arXiv title search per missing paper
    (scripts/link_arxiv.py, cached).
  * arXiv rows get a real venue when their own arXiv comment / journal-ref
    names one ("ICML 2026 Position Paper Track"), since AGENTS.md asks for
    "another venue if found".
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402
import link_arxiv  # noqa: E402
import tag_topics  # noqa: E402

RAWS = [
    ("icml2024_position_track", "ICML", 2024),
    ("icml2025_position_track", "ICML", 2025),
    ("icml2026_position_track", "ICML", 2026),
    ("neurips2025_position_track", "NeurIPS", 2025),
    ("neurips2026_position_track", "NeurIPS", 2026),
    ("arxiv_position_titles", "arXiv", None),
]

VENUE_MENTION = re.compile(
    r"\b(ICML|NeurIPS|ICLR|AAAI|COLM|ACL|EMNLP|UAI|AISTATS|FAccT|AIES|CVPR|ICCV|CHI|SIGIR)"
    r"\s*['\-]?\s*(20\d{2})\b", re.I)
POSITION_MENTION = re.compile(r"position\s*(?:paper)?\s*track|position\s*paper", re.I)
WORKSHOP = re.compile(r"workshop|tutorial|consortium", re.I)
CURATED = os.path.join(C.DATA, "curated", "stances.jsonl")
FILTER = os.path.join(C.DATA, "curated", "filter.jsonl")
CITATIONS = os.path.join(C.DATA, "citations.json")


def load_citations() -> dict[str, dict]:
    if not os.path.exists(CITATIONS):
        return {}
    with open(CITATIONS, encoding="utf-8") as fh:
        snapshot = json.load(fh)
    if snapshot.get("source") != "OpenAlex" or not snapshot.get("fetched_at"):
        raise ValueError("invalid citation snapshot")
    papers = snapshot.get("papers", {})
    for paper_id, record in papers.items():
        if not isinstance(record.get("citations"), int) or record["citations"] < 0:
            raise ValueError(f"invalid citation count for {paper_id}")
        if not record.get("openalex_id") or record.get("matched_by") not in {"arxiv_doi", "exact_title"}:
            raise ValueError(f"invalid OpenAlex match for {paper_id}")
    return papers


def load_exclusions() -> dict[str, dict]:
    if not os.path.exists(FILTER):
        return {}
    exclusions = {}
    with open(FILTER, encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            paper_id = record.get("id", "")
            if not paper_id or paper_id in exclusions:
                raise ValueError(f"missing or duplicate exclusion id at line {line_number}: {paper_id!r}")
            if record.get("exclude") is not True or not record.get("reason", "").strip():
                raise ValueError(f"invalid exclusion at line {line_number}")
            exclusions[paper_id] = record
    return exclusions


def load_curated() -> dict[str, dict]:
    if not os.path.exists(CURATED):
        return {}
    curated = {}
    with open(CURATED, encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            paper_id = record.get("id", "")
            if not paper_id or paper_id in curated:
                raise ValueError(f"missing or duplicate curated id at line {line_number}: {paper_id!r}")
            if record.get("confidence") not in {"high", "medium", "low"}:
                raise ValueError(f"invalid curated confidence at line {line_number}")
            if not record.get("stance_summary", "").strip() or not record.get("topic", "").strip():
                raise ValueError(f"empty curated stance or topic at line {line_number}")
            curated[paper_id] = record
    return curated


def venue_from_comment(row: dict) -> tuple[str, int, str] | None:
    """(venue, year, track) if the paper's own arXiv comment names a venue."""
    note = f"{row.get('journal_ref') or ''} {row.get('comment') or ''}"
    if not note.strip():
        return None
    best = None
    for m in VENUE_MENTION.finditer(note):
        acronym, year = m.group(1).upper(), int(m.group(2))
        acronym = {"ICML": "ICML", "NEURIPS": "NeurIPS", "ICLR": "ICLR"}.get(acronym, acronym)
        around = note[max(0, m.start() - 90):m.end() + 90]
        is_position = bool(POSITION_MENTION.search(around))
        in_workshop = bool(WORKSHOP.search(around))
        rank = (0 if is_position else 1, 1 if in_workshop else 0)
        if best is None or rank < best[0]:
            best = (rank, acronym, year, "Position Paper Track" if is_position else "")
    if best is None:
        return None
    _, acronym, year, track = best
    if track == "" and WORKSHOP.search(note):
        return None  # a workshop mention alone is too weak to relabel the venue
    return acronym, year, track


def join_dump(title: str, dump: list[dict]) -> dict | None:
    """The arXiv dump entry for a venue title, decided without the network.

    scripts/link_arxiv.py already defines when an arXiv title counts as the
    same paper (identical normalised title, or one title a prefix of the other
    over at least eight words - a camera-ready title is often the arXiv title
    plus a subtitle). Reuse that rule here: it costs milliseconds against the
    253-row dump and saves a 3-second API call per paper.
    """
    for rec in dump:
        if link_arxiv.accepted(title, rec["title"]):
            return rec
    return None


def merge() -> tuple[list[dict], dict]:
    raws = {name: C.read_raw(f"{name}.json") for name, _, _ in RAWS}
    dump_rows = raws.get("arxiv_position_titles", [])

    rows: list[dict] = []
    by_key: dict[str, dict] = {}
    stats = {"sources": {}, "dups_dropped": 0, "arxiv_linked": 0, "arxiv_lookup_found": 0,
             "arxiv_lookup_missing": 0, "venue_upgraded": 0, "id_dups_dropped": 0,
             "curated": 0}

    def add(row: dict) -> None:
        key = C.norm_title(row["title"])
        if not key:
            return
        if key in by_key:
            stats["dups_dropped"] += 1
            return
        by_key[key] = row
        rows.append(row)
        stats["sources"][row["source"]] = stats["sources"].get(row["source"], 0) + 1

    for name, _, _ in RAWS:
        for r in raws.get(name, []):
            add(dict(r))

    # arXiv ids for the venue rows.
    for row in rows:
        if row["venue"] == "arXiv-only":
            row["arxiv_id"] = row.get("arxiv_id", "")
            continue
        hit = join_dump(row["title"], dump_rows)
        if hit:
            row["arxiv_id"] = hit["arxiv_id"]
            if not (row.get("abstract") or "").strip():
                row["abstract"] = hit["abstract"]
            stats["arxiv_linked"] += 1

    missing = [r for r in rows if r["venue"] != "arXiv-only" and not r.get("arxiv_id")]
    if missing:
        print(f"  resolving {len(missing)} venue papers without an arXiv title match ...")
        found = link_arxiv.lookup_titles([r["title"] for r in missing])
        for row in missing:
            hit = found.get(C.norm_title(row["title"]))
            if hit:
                row["arxiv_id"] = hit["arxiv_id"]
                if not row.get("abstract"):
                    row["abstract"] = hit["abstract"]
                stats["arxiv_lookup_found"] += 1
            else:
                stats["arxiv_lookup_missing"] += 1

    # Venue names taken from the arXiv comment of otherwise arXiv-only rows.
    for row in rows:
        if row["venue"] != "arXiv-only":
            continue
        upgrade = venue_from_comment(row)
        if upgrade:
            venue, year, track = upgrade
            row["venue"], row["year"] = venue, year
            row["track"] = track
            row["url"] = f"https://arxiv.org/abs/{row['arxiv_id']}"
            stats["venue_upgraded"] += 1

    # A paper can reach us twice under two different titles - the conference's
    # camera-ready title and the arXiv title it was scanned under - so the title
    # key cannot catch it. The arXiv id is the same paper, and the row that came
    # from a track list is the one worth keeping.
    by_id: dict[str, int] = {}
    keep: list[dict] = []
    for row in rows:
        row.setdefault("track", "")
        row.setdefault("arxiv_id", "")
        aid = row["arxiv_id"]
        if not aid or aid not in by_id:
            if aid:
                by_id[aid] = len(keep)
            keep.append(row)
            continue
        stats["id_dups_dropped"] += 1
        prev = keep[by_id[aid]]
        if prev["source"] == "arxiv_title_scan" and row["source"] != "arxiv_title_scan":
            keep[by_id[aid]] = row  # the track row carries the venue metadata
    rows = keep
    stats["sources"] = {}
    for row in rows:
        stats["sources"][row["source"]] = stats["sources"].get(row["source"], 0) + 1

    for row in rows:
        row["url"] = row.get("url") or f"https://arxiv.org/abs/{row['arxiv_id']}"
        row["citations"] = ""
        row["authors"] = re.sub(r"\s+", " ", row.get("authors") or "").strip()

    tag_topics.tag_rows(rows)
    for row in rows:
        row["id"] = C.make_id(row["title"], row.get("arxiv_id", ""))
        row["year"] = int(row["year"])

    curated = load_curated()
    row_ids = {row["id"] for row in rows}
    unknown = set(curated) - row_ids
    if unknown:
        raise ValueError(f"curated ids not present in the dataset: {sorted(unknown)}")
    for row in rows:
        if record := curated.get(row["id"]):
            row["stance_summary"] = record["stance_summary"].strip()
            row["topic"] = record["topic"].strip()
            stats["curated"] += 1

    exclusions = load_exclusions()
    unknown = set(exclusions) - row_ids
    if unknown:
        raise ValueError(f"excluded ids not present in the dataset: {sorted(unknown)}")
    by_row_id = {row["id"]: row for row in rows}
    for paper_id, record in exclusions.items():
        duplicate_of = record.get("duplicate_of")
        if duplicate_of and duplicate_of not in row_ids:
            raise ValueError(f"duplicate target not present for {paper_id}: {duplicate_of}")
        if duplicate_of in exclusions:
            raise ValueError(f"duplicate target is also excluded for {paper_id}: {duplicate_of}")
    for row in rows:
        record = exclusions.get(row["id"])
        row["excluded"] = "true" if record else "false"
        if record and record.get("duplicate_of"):
            keeper = by_row_id[record["duplicate_of"]]
            if row.get("arxiv_id") and not keeper.get("arxiv_id"):
                keeper["arxiv_id"] = row["arxiv_id"]
    stats["excluded"] = len(exclusions)

    citations = load_citations()
    for row in rows:
        record = citations.get(row["id"])
        row["citations"] = record["citations"] if record else ""
    stats["citations"] = sum(row["id"] in citations for row in rows)

    rows.sort(key=lambda r: (-r["year"], r["venue"], r["title"].lower()))
    return rows, stats


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=os.path.join(C.DATA, "papers.csv"))
    args = ap.parse_args()

    rows, stats = merge()
    C.write_csv(rows, args.out)
    print(f"  wrote {len(rows)} rows -> {os.path.relpath(args.out, C.REPO)}")
    print(f"    curated stance/topic overrides: {stats['curated']}; automatic drafts retained: "
          f"{len(rows) - stats['curated']}; excluded from public views: {stats['excluded']}; "
          f"OpenAlex citations: {stats['citations']}")
    for src, n in stats["sources"].items():
        print(f"    {n:4d}  {src}")
    print(f"    duplicates dropped: {stats['dups_dropped']} by title, "
          f"{stats['id_dups_dropped']} by arXiv id; arXiv ids joined: "
          f"{stats['arxiv_linked']}+{stats['arxiv_lookup_found']} "
          f"(unresolved {stats['arxiv_lookup_missing']}), venue upgraded from arXiv comment: "
          f"{stats['venue_upgraded']}")


if __name__ == "__main__":
    main()
