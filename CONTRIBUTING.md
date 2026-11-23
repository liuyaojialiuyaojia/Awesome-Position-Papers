# Contributing

Thanks for helping. Three rules cover most of it:

1. **The READMEs are generated.** Never edit the paper tables in `README.md` or
   `README_zh.md` — change the data and rerun `scripts/build_readme.py`.
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
| `topic`, `stance_summary` | auto-drafted — see below |
| `citations` | usually empty: Semantic Scholar is rate-limited without a key (see `REPORT.md`) |
| `source` | which collector produced the row; do not hand it off |

Deduplication runs twice: on the normalised title
(`scripts/common.py:norm_title`) and, after the arXiv ids are joined, on the id
itself — a track's camera-ready title is often not the title the paper was
uploaded to arXiv under, and the id is what proves they are one paper. The
track row wins, because it carries the venue metadata.

## Fixing topics and stance summaries

Both are deterministic drafts, not ground truth:

- `topic` — keyword scores from [`data/taxonomy.yaml`](data/taxonomy.yaml); title
  hits weigh `title_boost`× an abstract hit, the venue's own category adds
  `native_boost`×, highest score wins, ties go to the earlier topic in the file.
  Add a keyword (or move a topic's position) rather than special-casing a paper.
- `stance_summary` — the paper's own claim sentence, with the framing stripped
  ("we argue that …", "this position paper contends that …"), else the first
  normative sentence ("X should …"), else the first judgement sentence
  ("X remains insufficient …"), else the title clause marked **(from title)**.
  A candidate with no finite verb is rejected and the next one is tried, so no
  fragment reaches the README. If it still reads badly, the abstract's own
  phrasing is worth quoting manually in a PR to `tag_topics.py`; run
  `scripts/stance_report.py` to see how the whole corpus scores.

After editing either, rerun:

```bash
.venv/bin/python scripts/tag_topics.py     # re-tags data/papers.csv in place
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
HTTP goes through `urllib` in `scripts/common.py`. No model APIs — the tagging
must stay auditable as rules in a text file.
