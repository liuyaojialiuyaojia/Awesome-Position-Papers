"""Shared helpers: polite HTTP with on-disk caching, CSV I/O, normalisation.

Every collector in this repo goes through http_get() so that reruns read from
.cache/ instead of re-hitting the APIs.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(REPO, ".cache")
RAW = os.path.join(CACHE, "raw")
DATA = os.path.join(REPO, "data")
RAW_DIR = os.path.join(DATA, "raw")
ASSETS = os.path.join(REPO, "assets")

USER_AGENT = "awesome-position-papers/1.0 (research dataset builder; contact via GitHub)"

COLUMNS = [
    "id", "title", "authors", "year", "venue", "track", "arxiv_id", "url",
    "abstract", "topic", "stance_summary", "citations", "source", "excluded",
]


def _ensure_dirs() -> None:
    for d in (CACHE, RAW, DATA, RAW_DIR, ASSETS):
        os.makedirs(d, exist_ok=True)


def cache_path(name: str) -> str:
    return os.path.join(RAW, name)


def read_cache(name: str):
    p = cache_path(name)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as fh:
            return fh.read()
    return None


def write_cache(name: str, text: str) -> None:
    _ensure_dirs()
    with open(cache_path(name), "w", encoding="utf-8") as fh:
        fh.write(text)


def http_get(url: str, cache_name: str | None = None, min_interval: float = 3.0,
             retries: int = 4, timeout: int = 60) -> str:
    """GET url, optionally serving from cache. Sleeps and backs off politely."""
    if cache_name:
        hit = read_cache(cache_name)
        if hit is not None:
            return hit

    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}
    last_err = None
    for attempt in range(retries):
        time.sleep(min_interval)
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", "replace")
            break
        except urllib.error.HTTPError as exc:  # noqa: PERF203
            last_err = exc
            if exc.code == 429 or exc.code >= 500:
                wait = min(60.0, min_interval * 4 * (2 ** attempt))
                print(f"    HTTP {exc.code} -> sleeping {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
                continue
            raise
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            time.sleep(min_interval * (2 ** attempt))
    else:
        raise RuntimeError(f"failed after {retries} tries: {url} ({last_err})")

    if cache_name:
        write_cache(cache_name, body)
    return body


# ---------------------------------------------------------------- normalising


def strip_tags(html: str) -> str:
    html = re.sub(r"<[^>]+>", " ", html or "")
    html = (html.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#x27;", "'").replace("&#39;", "'")
                .replace("&apos;", "'").replace("&nbsp;", " ").replace("&#x2F;", "/"))
    return re.sub(r"\s+", " ", html).strip()


def norm_title(title: str) -> str:
    """Aggressive key for dedup: lowercase alphanumerics only."""
    t = strip_tags(title or "")
    t = t.replace("$", "").lower()
    return re.sub(r"[^a-z0-9]+", "", t)


def slugify(text: str, maxlen: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return s[:maxlen].rstrip("-")


def hash_of(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def make_id(title: str, arxiv_id: str = "") -> str:
    """Stable row id: arXiv id when known, else a hash of the normalised title."""
    if arxiv_id:
        return arxiv_id.replace("/", "-")
    return "x" + hashlib.sha1(norm_title(title).encode("utf-8")).hexdigest()[:12]


# ------------------------------------------------------------------ yaml-lite
# data/taxonomy.yaml uses a deliberately small subset of YAML: nested mappings
# and lists of scalars. These two helpers parse exactly that subset, which
# keeps the dependency list to requests/pandas/matplotlib.


def load_taxonomy(path: str | None = None) -> dict:
    path = path or os.path.join(DATA, "taxonomy.yaml")
    tokens = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            tokens.append((len(line) - len(line.lstrip(" ")), line.strip()))
    value, _ = _parse_block(tokens, 0, tokens[0][0])
    return value


def _parse_block(tokens: list[tuple[int, str]], i: int, indent: int):
    if tokens[i][1].startswith("- "):
        items: list = []
        while i < len(tokens) and tokens[i][0] == indent and tokens[i][1].startswith("- "):
            items.append(_scalar(tokens[i][1][2:].strip()))
            i += 1
        return items, i

    node: dict = {}
    while i < len(tokens) and tokens[i][0] == indent and not tokens[i][1].startswith("- "):
        key, _, rest = tokens[i][1].partition(":")
        key, rest = key.strip().strip("\"'"), rest.strip()
        i += 1
        if rest:
            node[key] = _scalar(rest)
        elif i < len(tokens) and tokens[i][0] > indent:
            node[key], i = _parse_block(tokens, i, tokens[i][0])
        else:
            node[key] = None
    return node, i


def _scalar(text: str):
    if text.startswith(("\"", "'")) and text.endswith(text[0]) and len(text) > 1:
        return text[1:-1]
    low = text.lower()
    if low in ("true", "false"):
        return low == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


# ------------------------------------------------------------------------ csv


def write_csv(rows: list[dict], path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in COLUMNS})


def read_csv(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def write_json(obj, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def read_json(name: str):
    hit = read_cache(name)
    return json.loads(hit) if hit else None


def read_raw(name: str) -> list[dict]:
    """Read an intermediate produced by a collector (data/raw/<name>)."""
    path = os.path.join(RAW_DIR, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing - run the collectors first "
                                f"(see REPORT.md for the command order)")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def write_raw(name: str, rows: list[dict]) -> str:
    _ensure_dirs()
    path = os.path.join(RAW_DIR, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    return path


CARD_TITLE = re.compile(
    r'<h3 class="event-title">\s*<a href="(?P<href>[^"]*/)(?P<id>\d+)(?P<tail>[^"]*)">', re.S)
CARD_SPEAKERS = re.compile(r'<div class="event-speakers">(?P<s>.*?)</div>', re.S)
CARD_BADGE = re.compile(r'<span class="event-type-badge">([^<]*)</span>')
PAGE_ABSTRACT = re.compile(r'class="abstract-text-inner"[^>]*>(?P<a>.*?)</div>', re.S)
SPEAKER_SEP = re.compile(r"\s*[⋅·]\s*")


def event_cards(html: str, host: str) -> list[dict]:
    """Parse the event cards of an icml.cc / neurips.cc virtual-site track page.

    Both sites are the same platform: one <h3 class="event-title"> per accepted
    paper, with the speakers and the Poster/Oral badge in the rest of the card.
    """
    out: list[dict] = []
    for m in CARD_TITLE.finditer(html or ""):
        href = f"{m.group('href')}{m.group('id')}{m.group('tail')}"
        end = html.find("</a>", m.end())
        title = strip_tags(html[m.end():end if end > 0 else m.end()])
        tail = html[end:end + 1500] if end > 0 else ""
        sp = CARD_SPEAKERS.search(tail)
        authors = ""
        if sp:
            authors = ", ".join(a.strip() for a in
                                SPEAKER_SEP.split(strip_tags(sp.group("s"))) if a.strip())
        badge = CARD_BADGE.search(tail)
        out.append({
            "virtual_id": m.group("id"),
            "title": title,
            "authors": authors,
            "presentation": (badge.group(1).strip().lower() if badge else ""),
            "url": f"{host}{href.split('?')[0]}",
        })
    return out


def page_abstract(url: str, cache_name: str, min_interval: float = 2.0) -> str:
    """Abstract from a virtual-site paper page (2026 exports ship none)."""
    html = http_get(url, cache_name=cache_name, min_interval=min_interval)
    m = PAGE_ABSTRACT.search(html or "")
    return strip_tags(m.group("a")) if m else ""


def arxiv_entries(xml_text: str) -> list[dict]:
    """Parse an arXiv Atom feed into plain dicts."""
    ns = {"a": "http://www.w3.org/2005/Atom", "x": "http://arxiv.org/schemas/atom"}
    out = []
    for e in ET.fromstring(xml_text).findall("a:entry", ns):
        def txt(tag, nsmap=ns):
            node = e.find(tag, nsmap)
            return strip_tags(node.text or "") if node is not None and node.text else ""

        abs_url = txt("a:id")
        m = re.search(r"abs/([^v]+)(v\d+)?$", abs_url)
        out.append({
            "arxiv_id": m.group(1) if m else abs_url,
            "latest_version": (m.group(2).lstrip("v") if m and m.group(2) else ""),
            "title": re.sub(r"\s+", " ", txt("a:title").strip()),
            "abstract": txt("a:summary"),
            "authors": [n.find("a:name", ns).text for n in e.findall("a:author", ns)
                        if n.find("a:name", ns) is not None],
            "published": txt("a:published"),
            "updated": txt("a:updated"),
            "categories": [c.get("term") for c in e.findall("a:category", ns)],
            "comment": txt("x:comment", ns),
            "journal_ref": txt("x:journal_ref", ns),
        })
    return out


def total_results(xml_text: str) -> int:
    m = re.search(r"<opensearch:totalResults[^>]*>\s*(\d+)", xml_text)
    return int(m.group(1)) if m else 0
