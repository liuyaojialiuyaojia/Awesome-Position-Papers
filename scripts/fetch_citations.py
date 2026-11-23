"""Fill citation counts from OpenAlex and save an auditable dated snapshot.

Matching uses batches of arXiv DOI aliases first, then exact normalised-title
matches for unresolved papers. Raw responses are cached under .cache/.

    .venv/bin/python scripts/fetch_citations.py
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402

API = "https://api.openalex.org/works"
SELECT = "id,doi,title,cited_by_count,publication_year,ids"
BATCH_SIZE = 50


def get_works(params: dict, cache_prefix: str, interval: float, retries: int = 5) -> list[dict]:
    url = f"{API}?{urllib.parse.urlencode(params)}"
    cache_name = f"{cache_prefix}_{C.hash_of(url)}.json"
    body = C.http_get(url, cache_name=cache_name, min_interval=interval,
                      retries=retries, timeout=60)
    return json.loads(body).get("results", [])


def normalise_arxiv(value: str) -> str:
    value = urllib.parse.urlsplit(value or "").path.lstrip("/")
    value = re.sub(r"^(?:abs|pdf)/", "", value)
    value = re.sub(r"\.pdf$", "", value)
    return re.sub(r"v\d+$", "", value).lower()


def work_arxiv_id(work: dict) -> str:
    ids = work.get("ids") or {}
    if ids.get("arxiv"):
        return normalise_arxiv(ids["arxiv"])
    doi = (work.get("doi") or "").lower()
    marker = "10.48550/arxiv."
    if marker in doi:
        return normalise_arxiv(doi.split(marker, 1)[1])
    return ""


def identifier_score(work: dict, rows: list[dict]) -> tuple[int, int, str]:
    titles = {C.norm_title(row["title"]) for row in rows}
    return (
        int(C.norm_title(work.get("title", "")) in titles),
        int(work.get("cited_by_count") or 0),
        work.get("id") or "",
    )


def match_arxiv(rows: list[dict], interval: float) -> dict[str, dict]:
    rows_by_arxiv: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("arxiv_id"):
            rows_by_arxiv.setdefault(normalise_arxiv(row["arxiv_id"]), []).append(row)

    arxiv_ids = sorted(rows_by_arxiv)
    chosen: dict[str, tuple[dict, tuple]] = {}
    for start in range(0, len(arxiv_ids), BATCH_SIZE):
        chunk = arxiv_ids[start:start + BATCH_SIZE]
        aliases = [f"https://doi.org/10.48550/arxiv.{arxiv_id}" for arxiv_id in chunk]
        works = get_works(
            {"filter": "doi:" + "|".join(aliases), "per-page": BATCH_SIZE,
             "select": SELECT},
            "openalex_arxiv", interval,
        )
        for work in works:
            arxiv_id = work_arxiv_id(work)
            if arxiv_id not in chunk:
                continue
            score = identifier_score(work, rows_by_arxiv[arxiv_id])
            if arxiv_id not in chosen or score > chosen[arxiv_id][1]:
                chosen[arxiv_id] = (work, score)
        print(f"  arXiv DOI batches: {min(start + BATCH_SIZE, len(arxiv_ids))}/{len(arxiv_ids)}")

    matches = {}
    for arxiv_id, (work, _) in chosen.items():
        for row in rows_by_arxiv[arxiv_id]:
            matches[row["id"]] = work
    return matches


def best_title_work(row: dict, works: list[dict]) -> dict | None:
    title = C.norm_title(row["title"])
    candidates = [work for work in works if C.norm_title(work.get("title", "")) == title]
    if not candidates:
        return None
    year = int(row["year"])

    def order(work: dict) -> tuple:
        work_year = work.get("publication_year")
        return (
            int(work_year != year),
            abs(work_year - year) if work_year else 10000,
            work.get("id") or "",
        )

    return min(candidates, key=order)


def match_titles(unresolved: list[dict], interval: float,
                 cached_only: bool) -> tuple[dict[str, dict], list[str]]:
    matches = {}
    deferred = []
    for index, row in enumerate(unresolved, 1):
        params = {"search": row["title"], "per-page": 25, "select": SELECT}
        cache_name = f"openalex_title_{C.hash_of(f'{API}?{urllib.parse.urlencode(params)}')}.json"
        if cached_only and C.read_cache(cache_name) is None:
            deferred.append(row["id"])
            continue
        try:
            works = get_works(params, "openalex_title", interval, retries=1)
        except (urllib.error.HTTPError, RuntimeError) as exc:
            print(f"  title search failed for {row['id']}: {exc}", file=sys.stderr)
            deferred.append(row["id"])
            continue
        work = best_title_work(row, works)
        if work:
            matches[row["id"]] = work
        if index % 25 == 0 or index == len(unresolved):
            print(f"  exact-title fallbacks: {index}/{len(unresolved)} searched; "
                  f"{len(matches)} matched; {len(deferred)} deferred")
    return matches, deferred


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=os.path.join(C.DATA, "papers.csv"))
    parser.add_argument("--out", default=os.path.join(C.DATA, "citations.json"))
    parser.add_argument("--interval", type=float, default=3.0,
                        help="minimum seconds between uncached requests")
    parser.add_argument("--cached-titles-only", action="store_true",
                        help="defer title searches without a cached response")
    args = parser.parse_args()

    rows = C.read_csv(args.csv)
    print(f"OpenAlex: {len(rows)} papers; {sum(bool(r.get('arxiv_id')) for r in rows)} arXiv ids")
    direct = match_arxiv(rows, args.interval)
    unresolved = [row for row in rows if row["id"] not in direct]
    print(f"  matched {len(direct)} rows by arXiv DOI; {len(unresolved)} need title search")
    title_matches, deferred = match_titles(unresolved, args.interval, args.cached_titles_only)

    papers = {}
    for row in rows:
        work = direct.get(row["id"]) or title_matches.get(row["id"])
        if not work:
            row["citations"] = ""
            continue
        method = "arxiv_doi" if row["id"] in direct else "exact_title"
        papers[row["id"]] = {
            "citations": int(work.get("cited_by_count") or 0),
            "openalex_id": work["id"],
            "matched_by": method,
        }
        row["citations"] = str(papers[row["id"]]["citations"])

    snapshot = {
        "source": "OpenAlex",
        "fetched_at": dt.date.today().isoformat(),
        "deferred_title_ids": sorted(deferred),
        "papers": {paper_id: papers[paper_id] for paper_id in sorted(papers)},
    }
    C.write_json(snapshot, args.out)
    C.write_csv(rows, args.csv)

    public = [row for row in rows if row.get("excluded", "").lower() != "true"]
    public_matched = sum(row["id"] in papers for row in public)
    print(f"  wrote {len(papers)}/{len(rows)} citation counts -> {os.path.relpath(args.out, C.REPO)}")
    print(f"  matched by arXiv DOI: {len(direct)}; exact title: {len(title_matches)}; "
          f"deferred title searches: {len(deferred)}")
    print(f"  public coverage: {public_matched}/{len(public)}; "
          f"total citations: {sum(p['citations'] for p in papers.values()):,}")


if __name__ == "__main__":
    main()
