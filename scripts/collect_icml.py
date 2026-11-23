"""Collect an ICML Position Paper Track into data/raw/.

Two mechanisms, because the conference publishes the track differently by year:

  2024, 2025  the virtual-site export, e.g.
              https://icml.cc/static/virtual/data/icml-2025-orals-posters.json.
              2025 tags the track in its `topic` field ("Position->Data", ...)
              and in the "Oral <n>B Positions: ..." session names; 2024 has
              neither, so there the track convention (every track paper is
              titled "Position: ...") is the only available signal.
  2026        the export carries no track marker and no abstracts at all, so
              the track's own page is used:
              https://icml.cc/virtual/2026/events/2026-position-papers
              which lists every accepted card (title, authors, slot); authors
              and the conference's own topic string are joined from the export
              and each abstract is read from the paper's own virtual page.

OpenReview's API is 403 from this machine (see REPORT.md), so no venue list
comes from there.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402

BASE = "https://icml.cc/static/virtual/data"
HOST = "https://icml.cc"
TRACK_PAGES = {2026: "/virtual/2026/events/2026-position-papers"}


def is_track(rec: dict, year: int) -> bool:
    title = str(rec.get("name", ""))
    topic = str(rec.get("topic") or "")
    session = str(rec.get("session") or "")
    if year == 2024:
        return bool(re.match(r"^\s*Position[:!?.]", title))
    return (topic.lower().startswith("position")
            or bool(re.search(r"\bPositions?\b", session))
            or bool(re.match(r"^\s*Position[:!?.]", title) and session.startswith("Oral")))


def export(year: int) -> list[dict]:
    raw = C.http_get(f"{BASE}/icml-{year}-orals-posters.json",
                     cache_name=f"icml-{year}-orals-posters.json", min_interval=2.0)
    return json.loads(raw)["results"]


def base_row(year: int) -> dict:
    return {"source": f"icml{year}_position_track", "year": year, "venue": "ICML",
            "track": "Position Paper Track"}


def collect_from_export(year: int) -> list[dict]:
    seen: dict[str, dict] = {}
    for rec in export(year):
        if not is_track(rec, year):
            continue
        title = C.strip_tags(rec.get("name", ""))
        key = C.norm_title(title)
        if not key:
            continue
        authors = ", ".join(a.get("fullname", "").strip()
                            for a in (rec.get("authors") or []) if a.get("fullname"))
        row = base_row(year) | {
            "title": title,
            "authors": authors,
            "url": f"{HOST}/virtual/{year}/poster/{rec.get('id')}",
            "abstract": C.strip_tags(rec.get("abstract", "")),
            "presentation": str(rec.get("eventtype") or "").lower(),
            "decision": str(rec.get("decision") or ""),
            "native_topic": str(rec.get("topic") or ""),
            "virtual_id": rec.get("id"),
            "uid": rec.get("uid"),
        }
        # One paper appears as both an oral slot and a poster slot; keep the
        # the richer abstract and remember "oral" if either slot was oral.
        prev = seen.get(key)
        if prev is None:
            seen[key] = row
        else:
            winner = dict(row) if len(row["abstract"]) > len(prev["abstract"]) else dict(prev)
            if "oral" in row["presentation"] or "oral" in prev["presentation"]:
                winner["presentation"] = "oral"
            seen[key] = winner
    return list(seen.values())


def collect_from_page(year: int) -> list[dict]:
    html = C.http_get(f"{HOST}{TRACK_PAGES[year]}",
                      cache_name=f"icml-{year}-positionpapers-page.html", min_interval=2.0)
    cards = C.event_cards(html, HOST)
    by_id: dict[str, dict] = {}
    for rec in export(year):
        by_id.setdefault(str(rec.get("id")), rec)

    rows: list[dict] = []
    for i, card in enumerate(cards, 1):
        rec = by_id.get(str(card["virtual_id"]), {})
        abstract = C.page_abstract(card["url"], f"icml-{year}-paper-{card['virtual_id']}.html")
        rows.append(base_row(year) | {
            "title": card["title"],
            "authors": card["authors"] or ", ".join(
                a.get("fullname", "").strip() for a in (rec.get("authors") or [])
                if a.get("fullname")),
            "url": card["url"],
            "abstract": abstract,
            "presentation": card["presentation"] or str(rec.get("eventtype") or "").lower(),
            "decision": str(rec.get("decision") or ""),
            "native_topic": str(rec.get("topic") or ""),
            "virtual_id": card["virtual_id"],
            "uid": rec.get("uid"),
        })
        if i % 25 == 0:
            print(f"    ICML {year} abstracts: {i}/{len(cards)}")
    print(f"    ICML {year} abstracts: {len(cards)}/{len(cards)}")
    return rows


def collect(year: int) -> list[dict]:
    rows = collect_from_page(year) if year in TRACK_PAGES else collect_from_export(year)
    seen: dict[str, dict] = {}
    for row in rows:
        seen.setdefault(C.norm_title(row["title"]), row)
    return list(seen.values())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, choices=[2024, 2025, 2026], required=True)
    args = ap.parse_args()

    rows = collect(args.year)
    path = C.write_raw(f"icml{args.year}_position_track.json", rows)
    print(f"ICML {args.year} position track: {len(rows)} unique papers -> "
          f"{os.path.relpath(path, C.REPO)}")


if __name__ == "__main__":
    main()
