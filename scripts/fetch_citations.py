"""Optional: fill the `citations` column from Semantic Scholar.

api.semanticscholar.org is rate-limited (HTTP 429) from this machine without an
API key, which is the normal case. This script therefore:

  * makes one batched POST for all arXiv ids (never one request per paper),
  * backs off patiently (default ~4 minutes total) only while it keeps getting
    429/5xx,
  * gives up cleanly, leaving `citations` empty and saying so, because an empty
    column is honest and a guessed number is not.

No key was available while building this dataset, so `citations` is empty in
the shipped CSV. Whether a key avoids the 429s has not been tested here; if you
have one, rerun and see:

    SEMANTIC_SCHOLAR_KEY=... .venv/bin/python scripts/fetch_citations.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402

BATCH = "https://api.semanticscholar.org/graph/v1/paper/batch"
FIELDS = "citationCount,title,year,externalIds"
CHUNK = 100


def post(ids: list[str], key: str, deadline: float) -> list[dict] | None:
    url = f"{BATCH}?{urllib.parse.urlencode({'fields': FIELDS})}"
    body = json.dumps({"ids": [f"arXiv:{i}" for i in ids]}).encode()
    headers = {"User-Agent": C.USER_AGENT, "Content-Type": "application/json"}
    if key:
        headers["x-api-key"] = key
    wait = 15.0
    while time.time() < deadline:
        try:
            req = urllib.request.Request(url, data=body, headers=headers)
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            if exc.code in (429, 500, 502, 503):
                print(f"    HTTP {exc.code}; backing off {wait:.0f}s", file=sys.stderr)
                time.sleep(wait)
                wait = min(wait * 2, 90.0)
                continue
            print(f"    HTTP {exc.code}: {exc.read()[:160]!r}", file=sys.stderr)
            return None
        except Exception as exc:  # noqa: BLE001
            print(f"    {type(exc).__name__}: {exc}", file=sys.stderr)
            time.sleep(wait)
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=os.path.join(C.DATA, "papers.csv"))
    ap.add_argument("--minutes", type=float, default=4.0, help="total back-off budget")
    args = ap.parse_args()

    key = os.environ.get("SEMANTIC_SCHOLAR_KEY", "")
    rows = C.read_csv(args.csv)
    ids = sorted({r["arxiv_id"] for r in rows if r.get("arxiv_id")})
    print(f"Semantic Scholar: {len(ids)} arXiv ids, "
          f"{'with API key' if key else 'no key (public limit)'}, "
          f"budget {args.minutes:.0f} min")

    deadline = time.time() + args.minutes * 60
    counts: dict[str, int] = {}
    for i in range(0, len(ids), CHUNK):
        chunk = ids[i:i + CHUNK]
        got = post(chunk, key, deadline)
        if got is None:
            print("  giving up: citations left empty (API unavailable from this host). "
                  "Re-run with SEMANTIC_SCHOLAR_KEY set.")
            return
        for entry in got:
            if not entry:
                continue
            arx = (entry.get("externalIds") or {}).get("ArXiv")
            if arx:
                counts[arx] = int(entry.get("citationCount") or 0)
        print(f"    {min(i + CHUNK, len(ids))}/{len(ids)} queried, "
              f"{len(counts)} with counts")
        time.sleep(2)

    filled = 0
    for r in rows:
        if r.get("arxiv_id") and r["arxiv_id"] in counts:
            r["citations"] = counts[r["arxiv_id"]]
            filled += 1
    C.write_csv(rows, args.csv)
    print(f"  citations filled for {filled}/{len(rows)} rows -> data/papers.csv")


if __name__ == "__main__":
    main()
