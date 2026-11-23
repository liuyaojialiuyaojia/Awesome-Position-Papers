# Contributing

Thanks for helping. Three rules cover most of it:

1. **The READMEs are generated.** Never edit `README.md` or `README_zh.md`
   directly — change the data or generator and rerun `scripts/build_readme.py`.
2. **Every number must be reproducible.** Anything shown in a README has to come
   from a script in `scripts/` that can be rerun, so new claims need a collector
   or a stats change, not prose.
3. **Be polite to the APIs.** Descriptive `User-Agent`, ≥3 s between requests,
   back off on `429`, and let responses land in `.cache/` (git-ignored) so reruns
   do not re-download.

## Adding or fixing a paper

Edit `data/papers.csv` by hand only for a genuinely missing row; otherwise fix
the collector so the next full run also produces it.

| Column | Rule |
|---|---|
| `id` | arXiv id when known (`2505.12345`), else `x` + 12-hex of the normalised title (`scripts/common.py:make_id`) |
| `title`, `authors`, `abstract` | as published; LaTeX is flattened by `scripts/tag_topics.py:clean_text` |
| `year`, `venue`, `track` | venue year wins over the arXiv submission year; `venue` is `ICML`, `NeurIPS`, `arXiv-only`, or another venue if the paper's own arXiv comment names one |
| `url` | arXiv abstract page when an id exists, else the official venue page |
| `topic`, `stance_summary` | curated draft from `data/curated/stances.jsonl`; automatic fallback for new papers — see below |
| `citations` | OpenAlex count from `data/citations.json`; empty when no DOI/arXiv or exact-title match exists |
| `source` | which collector produced the row; do not hand it off |
| `excluded` | `true` for reviewed rows hidden from public views; otherwise `false` |

Deduplication runs twice: on the normalised title
(`scripts/common.py:norm_title`) and, after the arXiv ids are joined, on the id
itself — a track's camera-ready title is often not the title the paper was
uploaded to arXiv under, and the id is what proves they are one paper. The
track row wins, because it carries the venue metadata.

To review possible duplicates, withdrawals, short abstracts, or out-of-scope arXiv
rows, run `.venv/bin/python scripts/filter_candidates.py`. Review only the flagged
rows in `data/filter_candidates.jsonl`; record confirmed exclusions with a reason
in `data/curated/filter.jsonl`, then rebuild. Excluded rows stay in the CSV.

## Fixing topics and stance summaries

The current drafts were written by Kimi-K3.1-Pro (via Qoder CLI) from the
abstracts. Edit the paper's row in `data/curated/stances.jsonl`:

- `stance_summary`: one faithful English claim sentence, at most 30 words, with
  no framing such as "this paper argues".
- `topic`: one label from [`data/taxonomy.yaml`](data/taxonomy.yaml); choose the
  most specific fit.
- `confidence`: `high`, `medium`, or `low` (use `low` when the abstract is too
  vague to support a clear claim).

New papers without a curated row receive automatic keyword-topic and extractive
stance drafts. After editing, rerun:

```bash
.venv/bin/python scripts/build_dataset.py
.venv/bin/python scripts/stats.py
.venv/bin/python scripts/build_readme.py
```

## Adding a venue

Copy the smallest collector that fits (`scripts/collect_icml.py`), keep the
output shape of `data/raw/*.json`, then register it in `RAWS` in
`scripts/build_dataset.py` — precedence is by list order, so put conference
tracks before arXiv. Anything you learn about a blocked API belongs in
`REPORT.md`.

## Scope

Position papers from AI/ML and adjacent venues: papers that argue a stance
(recommendations, critiques, taxonomy proposals, policy positions) rather than
present a method or result. Surveys and opinion blog posts are out. If a paper
is a methods paper with "position" in the abstract, it is out.

Keep dependencies where they are: `requirements.txt` is pandas + matplotlib, and
HTTP goes through `urllib` in `scripts/common.py`. Do not call external LLM APIs;
curated corrections are reviewable text in `data/curated/stances.jsonl`.
