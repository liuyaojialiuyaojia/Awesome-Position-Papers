# Changelog

## 2026-11-23 — Website

- Added `scripts/build_site.py`, which generates `docs/index.html` and `docs/papers.json` with 638 public papers, 40 essential reads, and 10 debates covering 23 paper entries. Excluded rows stay out of the site.
- Added local search, topic/venue/year filter chips, an Essential only toggle, newest/oldest year sorting, 40-card incremental rendering, expandable abstracts, essential-reading notes, and side-by-side debate positions. Citation sorting appears automatically when citation data exists; it is hidden while all counts are empty.
- Added self-contained responsive CSS/JavaScript, persistent light/dark themes, labelled controls, keyboard-focus styles, a skip link, live result counts, and single-column mobile cards. The site has no build-time or runtime dependencies, external assets, or trackers.
- Validated Python syntax, repeat generation, 638 unique public ids, complete paper text and URLs, curated id references, unique HTML ids, and conditional citation-sort generation.
- Known problems: a real Chromium session could not start in this minimal environment because GLib, NSS, X11, and other system libraries are absent. Browser interactions and visual rendering therefore remain unverified; static and data checks passed. GitHub Pages still needs to be enabled by the owner for public hosting.

## 2026-11-23 — README redesign

- Rewrote `scripts/build_readme.py` to generate concise English and Chinese reading guides from `papers.csv`, `stats.json`, `essentials.yaml`, and `debates.yaml`; regenerated both READMEs at 204 lines each.
- Replaced the 638-row per-topic tables, source/venue audit tables, long collector documentation, and two-chart overview with four badges, three key numbers, one topic-by-year chart, 40 essential reads grouped across 10 topics, and 10 collapsible debate cards covering 23 papers.
- Added one full-list website link, three-line build instructions, compact contribution/curation notes, and retained the CC BY 4.0 citation. Validated Python syntax, balanced cards, badge/chart counts, curated CSV ids, and removal of full-list tables.
- Known problems: `docs/index.html` is the next backlog item, so the website link is pending until that page exists. Selections and debate sides remain abstract-level editorial drafts.

## 2026-11-23 — Debate map

- Added `data/curated/debates.yaml` with 10 concrete debates and 23 unique public papers. Each debate has one question, one line of context, and two or three concise sides grounded in the papers’ abstracts.
- Checked 25 candidate abstracts and retained 23; dropped the autonomous-science pair because its claims addressed different time horizons rather than giving directly different answers. Seven debates contain two papers and three contain three.
- Validated debate structure, unique debate and paper ids, public CSV membership, required fields, and the 10–15 debate range.
- Known problems: this is an abstract-level editorial map, not a full-text review or evidence that authors directly responded to one another. The README and website do not consume the file yet; those are separate backlog items.

## 2026-11-23 — Essential reads

- Reviewed the curated stance lines for 638 public papers, shortlisted 82 candidates, read their abstracts, and selected 40 essential reads. Added `data/curated/essentials.yaml` with a four-part rubric and one concise rationale per paper.
- Covered all 10 topics: five Safety & alignment papers, three Multimodal & generative media papers, and four from each other topic. The selection spans 15 papers from 2024, 14 from 2025, and 11 from 2026.
- Removed redundant theses and retained direct contrasts where both sides were substantive, including social simulation and AI-assisted peer review. Validated every selected id against the shortlist and public CSV rows.
- Known problems: selection is an abstract-level editorial judgment, not a full-text review; citations were unavailable and played no role. The README and website do not consume the new file yet; those are separate backlog items.

## 2026-11-23 — Compress taxonomy

- Compressed 15 topics to 10 and removed the `Other` bucket. Added an explicit legacy mapping and paper-level split overrides in `data/taxonomy.yaml`; `scripts/compress_taxonomy.py` updated 443 of 647 curated rows and is idempotent.
- Merged data with compute, theory with language modelling and reasoning, and society with fairness and human-AI interaction. Six former `Other` rows were assigned from their curated stance lines: four to Research & open science, one to Evaluation & benchmarks, and one excluded row to Multimodal & generative media.
- Rebuilt the CSV, statistics, both charts, and both READMEs. The 638 public papers now fall into: Models, reasoning & theory 107; People & society 88; Evaluation & benchmarks 88; Data & compute 77; Safety & alignment 62; Agents & autonomy 54; Research & open science 48; Governance & policy 47; AI for science 42; Multimodal & generative media 25.
- Known problems: broader topics trade some granularity for scanability. Their automatic fallback keyword lists were merged deterministically, but future uncurated papers may still need manual topic review.

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
