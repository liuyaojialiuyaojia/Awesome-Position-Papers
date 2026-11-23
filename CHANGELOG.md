# Changelog

## 2026-11-23 — Filter candidates

- Added `scripts/filter_candidates.py` and `data/filter_candidates.jsonl`; heuristic checks flagged 24 of 647 rows: 14 near-duplicates, 9 weak position signals, and 1 withdrawal mention.
- Manually reviewed only the flagged rows. Excluded 9: seven duplicate arXiv/ICML variants and two method papers (`2405.18236`, `2502.03876`). The withdrawal mention concerned a dataset, not the paper; no rows were cut for withdrawal or short abstracts.
- Added `data/curated/filter.jsonl` and the CSV `excluded` column. All 647 rows remain in the CSV; stats, charts, and both READMEs now include 638 papers. Official conference rows retained from duplicate pairs inherit their arXiv ids.
- Known problems: candidate rules are heuristic and do not prove scope or duplication; unflagged rows were not re-audited. The website does not exist yet, so there was no site output to filter.

## 2026-11-23 — Task v3: model-written stances and topics

- Read all 647 titles and abstracts; added 647 curated rows in `data/curated/stances.jsonl` across 26 resumable batches.
- Added stable-id curated overrides to `scripts/build_dataset.py`; all 647 current papers use curated stances/topics, while future uncurated papers retain automatic drafts.
- Confidence: 647 high, 0 medium, 0 low. Every stance is one English sentence of at most 24 words; all 15 existing topics remain in use and the taxonomy is unchanged.
- Rebuilt `data/papers.csv`, `data/stats.json`, both charts, and both READMEs. Largest topics are Evaluation & benchmarks (87), Foundations & theory (74), and Safety & alignment (62); Other & cross-cutting fell from 36 to 6.
- Added reproducible confidence, topic-distribution, and 20-sample old/new reporting through `scripts/curation_report.py`; updated `REPORT.md` and contribution instructions.
- Known problems: curated judgments remain drafts pending review; duplicate variants, withdrawn papers, and out-of-scope papers have not yet been filtered. Citations remain empty.
