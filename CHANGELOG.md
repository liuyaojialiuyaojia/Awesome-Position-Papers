# Changelog

## 2026-11-23 — Task v3: model-written stances and topics

- Read all 647 titles and abstracts; added 647 curated rows in `data/curated/stances.jsonl` across 26 resumable batches.
- Added stable-id curated overrides to `scripts/build_dataset.py`; all 647 current papers use curated stances/topics, while future uncurated papers retain automatic drafts.
- Confidence: 647 high, 0 medium, 0 low. Every stance is one English sentence of at most 24 words; all 15 existing topics remain in use and the taxonomy is unchanged.
- Rebuilt `data/papers.csv`, `data/stats.json`, both charts, and both READMEs. Largest topics are Evaluation & benchmarks (87), Foundations & theory (74), and Safety & alignment (62); Other & cross-cutting fell from 36 to 6.
- Added reproducible confidence, topic-distribution, and 20-sample old/new reporting through `scripts/curation_report.py`; updated `REPORT.md` and contribution instructions.
- Known problems: curated judgments remain drafts pending review; duplicate variants, withdrawn papers, and out-of-scope papers have not yet been filtered. Citations remain empty.
