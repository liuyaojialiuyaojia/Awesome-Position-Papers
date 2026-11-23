# Report — Task v1

This file documents the first full build of the dataset: what was collected,
how many papers each source produced, which sources failed, known gaps, and
the exact commands to rerun everything.

## What was done

1. **Collected** position papers from four sources in order of precedence:
   - ICML 2024 Position Paper Track (conference virtual-site export)
   - ICML 2025 Position Paper Track (conference virtual-site export)
   - NeurIPS 2025 Position Paper Track (official track page + export)
   - arXiv titles starting with `Position:` / `Position Paper:` (Jan 2023 → today)
2. **Deduplicated** by normalised title so a paper that exists on arXiv and at a
   venue is a single row, keeping the venue metadata and gaining the arXiv id.
3. **Tagged** each paper with one primary topic from a 15-topic taxonomy
   (`data/taxonomy.yaml`) and a one-sentence stance draft from the abstract.
4. **Generated** `data/stats.json`, two charts in `assets/`, and both READMEs
   from the CSV via `scripts/build_readme.py`.
5. **Attempted** Semantic Scholar citation counts (optional, see below).
6. **Added** `LICENSE` (CC BY 4.0), `CONTRIBUTING.md`, `requirements.txt`.

## Counts per source

| Source | Unique papers |
|---|---|
| ICML 2024 position track | 75 |
| ICML 2025 position track | 72 |
| NeurIPS 2025 position track | 40 |
| arXiv title scan (Jan 2023 → today) | 253 |
| **Total before dedup** | **440** |
| After dedup (same paper on arXiv and at a venue = one row) | **382** |

Final counts (from `data/stats.json`):
- Total papers: 382
- Topics: 15
- Years: 2023–2026
- With arXiv id: 328 (86%)
- Venue breakdown: ICML 208, NeurIPS 48, arXiv-only 123, ACL 2, EMNLP 1
- Source breakdown: arxiv_title_scan 195, icml2024_position_track 75, icml2025_position_track 72, neurips2025_position_track 40
- Duplicates dropped: 58
- Venue rows with arXiv ids joined: 58 (from dump) + 75 (from targeted lookup) = 133
- Venue rows without arXiv ids: 54 (no arXiv version found)
- arXiv-only rows upgraded to a venue from their own comment: 72 (mostly ICML/NeurIPS 2026)

## How each source was identified

### ICML 2024

The conference's virtual-site export (`icml-2024-orals-posters.json`) has no
explicit track tag. ICML 2024's position-track papers were identified by the
track convention that every position-track paper is titled `Position: ...`. The
`/notes` endpoint of OpenReview's API is 403 from this machine, so we could not
cross-check against an official venue-group id.

### ICML 2025

The 2025 export uses a dedicated topic prefix `Position->Methodology`,
`Position->Risk_safety_policy`, `Position->Social_ethical_env_impact`,
`Position->Understanding`, `Position->Data`, `Position->Other`. Papers in the
`Oral <n>B Positions: ...` oral sessions were included even when their topic
field was unset. Union of both rules: 72 unique papers (the conference reported
71 accepted; the off-by-one is a duplicate variant between the two session
listings).

### NeurIPS 2025

The export has no track tag and only 8 of the 40 accepted position papers are
titled `Position: ...`, so title matching would miss most of the track. Instead
we scraped the conference's own track page
`https://neurips.cc/virtual/2025/events/positionpapers2025` for the 40 paper
gids and joined them against the export for authors and abstracts.

### arXiv

Bulk query `ti:"Position" AND submittedDate:[202301010000 TO <today>]` paginated
in chunks of 300 (arXiv stems `ti:` so the feed also returns "positioning",
"positivity", "superposition", ...). The local filter keeps only titles that
start with `Position:` or `Position Paper:` — hyphenated look-alikes like
"Position-Aware ..." are excluded. 253 unique titles after dedup by normalised
title.

## What failed

- **OpenReview API (`api2.openreview.net`)** — HTTP 403 for `/notes` even with a
  browser `User-Agent`. `/notes/search` works but cannot enumerate a venue's
  accepted list. We did not use it for the authoritative venue lists.
- **Semantic Scholar (`api.semanticscholar.org`)** — HTTP 429 on both the
  single-paper and batch endpoints even after several minutes of back-off.
  **No API key was available in this environment, so it was never tested with
  one**: the `citations` column is empty, which is the honest outcome rather
  than a guessed number. To fill it, rerun
  `SEMANTIC_SCHOLAR_KEY=... .venv/bin/python scripts/fetch_citations.py` on a
  machine that has a key.

## Known gaps

- **ICML 2024** — any position-track paper whose title does not begin with
  `Position:` is missed (the track convention is required titles to start with
  that prefix, but a handful of main-track papers with `Position:` titles may
  also be picked up; the dedup rule keeps whichever was seen first).
- **ICML 2025** — the 72 papers are the union of the topic-tagged set and the
  `Positions:` oral sessions; the conference reported 71 accepted, so we may
  have one duplicate variant.
- **NeurIPS 2025** — the 40 gids on the track page are the full accepted list
  as of the page's last update; if the page is updated after a late acceptance
  the script will pick it up on rerun.
- **arXiv** — only titles starting with `Position:` / `Position Paper:` are
  collected. Position papers that chose a different title prefix are missed.
  The date window is 2023-01 to today; earlier position papers are out of scope.
- **Topic tagging** — purely keyword-based, deterministic, no model calls.
  Wrong tags are expected; edit `data/taxonomy.yaml` and rerun
  `scripts/tag_topics.py`.
- **Stance summaries** — extractive: first abstract sentence with a stance cue,
  else first normative sentence, else the title clause. Clumsy phrasing is
  expected; the summaries are drafts.
- **Citations** — empty (Semantic Scholar 429).

## Rerun commands

From the repo root, with a fresh venv:

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python scripts/collect_icml.py --year 2024
.venv/bin/python scripts/collect_icml.py --year 2025
.venv/bin/python scripts/collect_neurips.py
.venv/bin/python scripts/collect_arxiv.py
.venv/bin/python scripts/build_dataset.py
.venv/bin/python scripts/fetch_citations.py   # optional; gives up cleanly on 429
.venv/bin/python scripts/stats.py
.venv/bin/python scripts/build_readme.py
```

Second runs are near-instant because every raw API response is cached under
`.cache/` (git-ignored). To force a fresh download, delete `.cache/`.

## Files produced

```
data/
  papers.csv          # one row per deduplicated paper
  stats.json          # counts, years, charts list
  taxonomy.yaml       # the 15-topic taxonomy
  raw/                # intermediate collector outputs (git-ignored)
assets/
  papers_per_topic.png
  papers_per_topic_by_year_venue.png
scripts/
  common.py           # HTTP cache, CSV I/O, YAML-lite parser
  collect_icml.py
  collect_neurips.py
  collect_arxiv.py
  link_arxiv.py
  build_dataset.py
  tag_topics.py
  stats.py
  build_readme.py
  fetch_citations.py
README.md             # English
README_zh.md          # Chinese, Xiaohongshu-style tone
CONTRIBUTING.md
LICENSE               # CC BY 4.0
requirements.txt
REPORT.md             # this file
```
