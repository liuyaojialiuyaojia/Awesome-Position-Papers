"""Targeted arXiv title lookups, used to give venue papers an arXiv id.

One query per paper, cached under .cache/raw/arxiv-lookup-<sha1>.xml, so a
second run of build_dataset.py makes no requests at all. A hit is accepted
only when the arXiv title is the same paper: identical normalised title, or
one title being a prefix of the other over at least 8 words (venue cameras
sometimes append a subtitle).
"""

from __future__ import annotations

import re
import sys
import urllib.parse

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402

API = "https://export.arxiv.org/api/query"
STRIP_PREFIX = re.compile(r"^\s*(?:position(?:\s+paper)?|a?\s*position)\s*[:\-!?.]\s*", re.I)


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def accepted(venue_title: str, arxiv_title: str) -> bool:
    a, b = _words(STRIP_PREFIX.sub("", venue_title)), _words(STRIP_PREFIX.sub("", arxiv_title))
    if not a or not b:
        return False
    if C.norm_title(venue_title) == C.norm_title(arxiv_title):
        return True
    n = min(len(a), len(b))
    if n >= 8 and a[:n] == b[:n]:
        return True
    return False


def lookup(title: str) -> dict | None:
    core = STRIP_PREFIX.sub("", title).strip().rstrip(":")
    words = core.split()
    phrases = [core, " ".join(words[:9])] if len(words) > 9 else [core]
    for attempt, phrase in enumerate(dict.fromkeys(p for p in phrases if p)):
        params = {"search_query": f'ti:"{phrase}"', "start": 0, "max_results": 20}
        url = f"{API}?{urllib.parse.urlencode(params)}"
        cache = f"arxiv-lookup-{C.hash_of(url)}.xml"
        xml = C.http_get(url, cache_name=cache, min_interval=3.2)
        for e in C.arxiv_entries(xml):
            if accepted(title, e["title"]):
                return {"arxiv_id": e["arxiv_id"], "title": e["title"],
                        "abstract": re.sub(r"\s+", " ", e["abstract"]).strip(),
                        "published": e["published"][:10],
                        "url": f"https://arxiv.org/abs/{e['arxiv_id']}"}
        if "<entry>" not in xml and attempt == 0:
            break
    return None


def lookup_titles(titles: list[str]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i, t in enumerate(titles, 1):
        hit = lookup(t)
        if hit:
            out[C.norm_title(t)] = hit
        if i % 10 == 0:
            print(f"    arXiv lookups: {i}/{len(titles)} ({len(out)} matched)")
    print(f"    arXiv lookups done: {i} queries, {len(out)} matched")
    return out


if __name__ == "__main__":
    for t in sys.argv[1:]:
        print(t, "->", lookup(t))
