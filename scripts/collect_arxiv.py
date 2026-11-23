"""Collect arXiv position papers by title (Jan 2023 -> today).

One bulk query is paginated instead of one query per paper:

    search_query=ti:"Position" AND submittedDate:[202301010000 TO <today>]

arXiv stems `ti:` matches, so the feed also returns "positioning",
"positivity", "superposition", ...; those are dropped by the local title
filter. Each page is cached under .cache/raw/ so reruns are free.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import sys
import urllib.parse

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402

API = "https://export.arxiv.org/api/query"
SINCE = "202301010000"
PAGE = 300
# arXiv title must open with a stance marker: "Position: ..." or the rarer
# "Position Paper: ...". Hyphenated look-alikes ("Position-Aware ...",
# "Position-dependent ...") are ordinary research titles and are excluded.
POSITION_TITLE = re.compile(r"^\s*Position(?:\s+Paper)?\s*:\s*\S", re.IGNORECASE)


def query(since: str, until: str) -> str:
    return f'ti:"Position" AND submittedDate:[{since} TO {until}]'


def fetch_pages(since: str, until: str) -> list[dict]:
    entries: list[dict] = []
    start, total = 0, None
    while True:
        params = {"search_query": query(since, until), "start": start, "max_results": PAGE,
                  "sortBy": "submittedDate", "sortOrder": "ascending"}
        url = f"{API}?{urllib.parse.urlencode(params)}"
        name = f"arxiv-ti-position-{start:05d}.xml"
        xml = C.http_get(url, cache_name=name, min_interval=3.5)
        page = C.arxiv_entries(xml)
        if total is None:
            total = C.total_results(xml)
            print(f"  arXiv reports {total} stem-matched titles (filtered locally)")
        if not page:
            break
        entries.extend(page)
        start += PAGE
        if start >= total:
            break
    return entries


def main() -> None:
    today = dt.date.today()
    until = (today + dt.timedelta(days=1)).strftime("%Y%m%d0000")
    print(f"arXiv window: {SINCE} .. {until}")
    entries = fetch_pages(SINCE, until)

    # Deduplicate by normalised title; the first submission date wins.
    by_key: dict[str, dict] = {}
    for e in entries:
        title = re.sub(r"\s+", " ", e["title"]).strip()
        if not POSITION_TITLE.match(title):
            continue
        key = C.norm_title(title)
        if key not in by_key or e["published"] < by_key[key]["published"]:
            by_key[key] = e

    out = []
    for e in by_key.values():
        title = re.sub(r"\s+", " ", e["title"]).strip()
        published = e["published"]
        out.append({
            "source": "arxiv_title_scan",
            "title": title,
            "authors": ", ".join(e["authors"]),
            "year": int(published[:4]),
            "venue": "arXiv-only",
            "track": "",
            "url": f"https://arxiv.org/abs/{e['arxiv_id']}",
            "abstract": re.sub(r"\s+", " ", e["abstract"]).strip(),
            "arxiv_id": e["arxiv_id"],
            "published": published[:10],
            "updated": e["updated"][:10],
            "categories": ", ".join(e["categories"]),
            "comment": e["comment"],
            "journal_ref": e["journal_ref"],
        })

    out.sort(key=lambda r: r["published"], reverse=True)
    path = C.write_raw("arxiv_position_titles.json", out)
    colon = sum(1 for r in out if re.match(r"^\s*Position\s*:", r["title"], re.I))
    print(f"arXiv: {len(entries)} stem matches -> {len(out)} unique stance-titled papers"
          f" ({colon} 'Position:', {len(out) - colon} 'Position Paper:')"
          f" -> {os.path.relpath(path, C.REPO)}")


if __name__ == "__main__":
    main()
