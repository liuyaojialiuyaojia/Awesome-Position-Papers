"""Collect a NeurIPS Position Paper Track into data/raw/.

The virtual-site export (neurips-<year>-orals-posters.json) covers every
conference paper but carries no track tag for position papers, and only a
minority of the track is titled "Position: ..." (8 of 40 in 2025), so title
matching would miss most of the track. Instead we read the conference's own
track page and join it to the export for the conference's topic string:

    https://neurips.cc/virtual/2025/events/positionpapers2025
    https://neurips.cc/virtual/2026/loc/<site>/events/position-papers-2026

NeurIPS 2026 splits its programme over three physical sites, each with its own
position-papers page holding a disjoint third of the track; all three are read.
The 2026 export ships no abstracts, so each abstract is taken from the paper's
own virtual page.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402

HOST = "https://neurips.cc"
BASE = "https://neurips.cc/static/virtual/data"
TRACK_PAGES = {
    2025: [("neurips-2025-positionpapers-page.html",
            "/virtual/2025/events/positionpapers2025")],
    2026: [(f"neurips-2026-positionpapers-page-{site}.html",
            f"/virtual/2026/loc/{site}/events/position-papers-2026")
           for site in ("sydney", "paris", "atlanta")],
}


def export(year: int) -> list[dict]:
    raw = C.http_get(f"{BASE}/neurips-{year}-orals-posters.json",
                     cache_name=f"neurips-{year}-orals-posters.json", min_interval=2.0)
    return json.loads(raw)["results"]


def track_ids(year: int) -> list[dict]:
    """Cards from every track page of that year, in page order, deduplicated."""
    out: list[dict] = []
    seen: set[str] = set()
    for cache_name, path in TRACK_PAGES[year]:
        html = C.http_get(f"{HOST}{path}", cache_name=cache_name, min_interval=2.0)
        for card in C.event_cards(html, HOST):
            if card["virtual_id"] not in seen:
                seen.add(card["virtual_id"])
                out.append(card)
    return out


def collect(year: int) -> list[dict]:
    cards = track_ids(year)
    by_id: dict[str, list[dict]] = {}
    for rec in export(year):
        by_id.setdefault(str(rec.get("id")), []).append(rec)

    rows = []
    for i, card in enumerate(cards, 1):
        gid = card["virtual_id"]
        recs = by_id.get(gid, [])
        if not recs:
            print(f"    warning: gid {gid} absent from the {year} export", file=sys.stderr)
        rec = max(recs, key=lambda r: len(str(r.get("abstract") or "")), default={})
        title = card["title"] or C.strip_tags(str(rec.get("name", "")))
        authors = card["authors"] or ", ".join(
            a.get("fullname", "").strip() for a in (rec.get("authors") or [])
            if a.get("fullname"))
        abstract = C.strip_tags(str(rec.get("abstract") or ""))
        if not abstract and card["url"]:
            abstract = C.page_abstract(card["url"], f"neurips-{year}-paper-{gid}.html")
        rows.append({
            "source": f"neurips{year}_position_track",
            "title": title,
            "authors": authors,
            "year": year,
            "venue": "NeurIPS",
            "track": "Position Paper Track",
            "url": card["url"] or f"{HOST}/virtual/{year}/poster/{gid}",
            "abstract": abstract,
            "presentation": card["presentation"] or str(rec.get("eventtype") or "").lower(),
            "decision": str(rec.get("decision") or ""),
            "native_topic": str(rec.get("topic") or ""),
            "virtual_id": gid,
            "uid": rec.get("uid"),
        })
        if i % 25 == 0:
            print(f"    NeurIPS {year} papers: {i}/{len(cards)}")
    print(f"    NeurIPS {year} papers: {len(cards)}/{len(cards)}")
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--year", type=int, choices=[2025, 2026], default=2025)
    args = ap.parse_args()

    rows = collect(args.year)
    path = C.write_raw(f"neurips{args.year}_position_track.json", rows)
    print(f"NeurIPS {args.year} position track: {len(rows)} papers -> "
          f"{os.path.relpath(path, C.REPO)}")


if __name__ == "__main__":
    main()
