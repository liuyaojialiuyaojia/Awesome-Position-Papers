# Report — Task v1

This file documents the first full build of the dataset: what was collected,
how many papers each source produced, which sources failed, known gaps, and
the exact commands to rerun everything.

## Candidate filtering (2026-11-23)

`scripts/filter_candidates.py` flags candidates without a model and writes `data/filter_candidates.jsonl`; it never excludes a row by itself. Only the 24 flagged rows were reviewed. Confirmed decisions live in `data/curated/filter.jsonl`.

| Candidate reason | Flagged | Excluded | Decision |
|---|---:|---:|---|
| Same arXiv id | 0 | 0 | No candidates in the initial dataset. |
| Near-identical title | 14 | 7 | Seven duplicate pairs confirmed from authors and abstracts; the official ICML row was kept and inherited the arXiv id. |
| Weak position signal | 9 | 2 | `2405.18236` and `2502.03876` present methods and experiments rather than position arguments. |
| Withdrawal mention | 1 | 0 | The abstract discusses withdrawal of a training dataset, not withdrawal of the paper. |
| Empty or very short abstract | 0 | 0 | No abstract was below 400 characters or 60 words. |
| **Total** | **24** | **9** | 15 candidates were retained. |

The CSV keeps all **647** rows with `excluded=true|false`; stats, charts, and both READMEs contain **638** included papers. Candidate generation remains stable after duplicate rows pass their arXiv ids to the retained conference rows. The website has not been built yet, so no website output existed to filter.

Rerun the filter and public outputs:

```bash
.venv/bin/python scripts/filter_candidates.py
# Review only data/filter_candidates.jsonl; update data/curated/filter.jsonl manually.
.venv/bin/python scripts/build_dataset.py
.venv/bin/python scripts/stats.py
.venv/bin/python scripts/build_readme.py
```

Known limitation: these are candidate heuristics, not exhaustive validation. Unflagged rows were not re-audited.

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

## v3 changes

Read all **647 abstracts** and wrote one curated stance, topic, and confidence value per paper in `data/curated/stances.jsonl`, in resumable batches of 25. Kimi-K3.1-Pro (via Qoder CLI) wrote the drafts directly; no external LLM API or keyword generator was used. The build now applies these rows by stable paper id, while future uncurated papers retain automatic drafts.

### Confidence

| Confidence | Papers |
|---|---:|
| high | 647 |
| medium | 0 |
| low | 0 |
| **Total** | **647** |

### Topic distribution

Before is `.cache/papers_v2.csv`; after is the rebuilt `data/papers.csv`.

| Topic | Before | After | Change |
|---|---:|---:|---:|
| Evaluation & benchmarks | 88 | 87 | -1 |
| Foundations & theory | 53 | 74 | +21 |
| Safety & alignment | 89 | 62 | -27 |
| Agents & autonomy | 77 | 55 | -22 |
| Data, provenance & ownership | 29 | 53 | +24 |
| Governance, regulation & policy | 28 | 47 | +19 |
| Human-AI interaction & usability | 32 | 46 | +14 |
| Open science, publishing & research culture | 14 | 44 | +30 |
| Scientific discovery & AI for science | 48 | 42 | -6 |
| Language models & reasoning | 15 | 37 | +22 |
| Multimodal, vision & generative media | 37 | 26 | -11 |
| Efficiency, scaling & sustainability | 17 | 25 | +8 |
| Fairness, bias & pluralism | 19 | 24 | +5 |
| Society, labor & economy | 65 | 19 | -46 |
| Other & cross-cutting | 36 | 6 | -30 |
| **Total** | **647** | **647** | **+0** |

### 20 random stance revisions

Deterministic sample from all 647 papers, seed `20261123`.

1. **Position: Foundation Agents as the Paradigm Shift for Decision Making** (`2405.17009`)
   - Old: We advocate for the construction of foundation agents as a transformative shift in the learning paradigm of agents.
   - New: Decision-making agents should adopt foundation-agent pretraining and adaptation to improve sample efficiency and generalization across tasks.

2. **Position: There Is No Free Bayesian Uncertainty Quantification** (`2506.03670`)
   - Old: There Is No Free Bayesian Uncertainty Quantification (from title)
   - New: Bayesian posterior distributions should not be interpreted as uncertainty quantification without assessing the inference stage and its optimization-based assumptions.

3. **Position: Stop Anthropomorphizing Intermediate Tokens as Reasoning/Thinking Traces!** (`2504.09762`)
   - Old: We call on the community to avoid such anthropomorphization of intermediate tokens.
   - New: Researchers should stop anthropomorphizing intermediate tokens as reasoning traces or thoughts because the metaphor mischaracterizes models and misguides research.

4. **Position: The Case for Theory-Level Autoformalization** (`x1efc0a5d0819`)
   - Old: The Case for Theory-Level Autoformalization (from title)
   - New: Autoformalization should target complete interdependent theories rather than isolated statements to build structured, machine-verifiable mathematical libraries.

5. **Position: Beyond Personhood: Agency, Accountability, and the Limits of Anthropomorphic Ethical Analysis** (`2404.13861`)
   - Old: In the context of ethically-significant behavior, AI should be viewed not as an agent but as the outcome of political processes.
   - New: Ethical analysis should treat AI as an outcome of political processes rather than an anthropomorphic moral agent when assigning accountability.

6. **Position: In Defense of Information Leakage in Concept-based Models** (`2606.10669`)
   - Old: This conventional view of leakage in CMs is not only ill-posed, as the evidence of how leakage makes a model less interpretable is often inconclusive, but also bound to lead to impractical CMs under common real-world constraints.
   - New: Concept leakage can be benign and necessary for accurate, intervenable concept-based models when real-world concept sets are incomplete.

7. **Position: Stop Acting Like Language Model Agents Are Normal Agents** (`2502.10420`)
   - Old: These assumptions are critical to prospective use cases in industrial, social and governmental settings.
   - New: Language-model agents should not be treated as normal agents; deployment should measure continuity, persistence, consistency, and identifiability.

8. **Position: Evaluations of AI Moral Reasoning Still Miss Half of the Picture** (`2608.14566`)
   - Old: Evaluations of AI Moral Reasoning Still Miss Half of the Picture (from title)
   - New: Moral-reasoning evaluation should test context-sensitive norm identification and application alongside alignment with human values.

9. **Position: Safety and Fairness in Agentic AI Depend on Interaction Topology, Not on Model Scale or Alignment** (`2605.01147`)
   - Old: This assumption is fundamentally mistaken.
   - New: Multi-agent safety evaluation and regulation should target interaction topology because aligned individual models do not ensure safe collective behavior.

10. **Position: Time to Close The Validation Gap in LLM Social Simulations** (`xc59d1e0c2bba`)
   - Old: The field must pivot from expansion to consolidation, prioritizing methodological standardization—shared benchmarks, open data, and reproducible evaluation protocols grounded in social science and complex systems research.
   - New: LLM social simulation should consolidate around shared benchmarks, open data, and reproducible social-science validation before high-stakes deployment.

11. **Position: AI Welfare Is Bullshit** (`x8eace02f6580`)
   - Old: AI Welfare Is Bullshit (from title)
   - New: AI welfare metrics lack external validation and should not gate releases, resist oversight, or justify restrictions without externally verifiable harms.

12. **Position: From Crowdsourcing to Crowd-LLM-Sourcing and LLM-Sourcing** (`x0afbbffc4d4d`)
   - Old: In scenarios where an LLM can be regarded as an LLM worker, LLM research should draw upon the rich body of crowdsourcing literature.
   - New: LLM research should adapt crowdsourcing mechanisms for model workers while accounting for fundamental differences between human and LLM workers.

13. **Position: LLM Agents Are the Antidote to Walled Gardens** (`2506.23978`)
   - Old: The ML community should embrace this development while building the appropriate frameworks to mitigate the downsides.
   - New: The ML community should embrace agent-enabled universal interoperability to weaken platform lock-in while building safeguards for security and technical debt.

14. **Position: Generative AI Regulation Can Learn from Social Media Regulation** (`2412.11335`)
   - Old: The debates on generative AI regulation can be informed by evidence on social media regulation.
   - New: Generative-AI regulation should adapt evidence from social-media governance on bias, trust, researcher access, specific harms, and global coordination.

15. **Language Models Can Benefit from Domain-Specific Inductive Biases** (`2611.03756`)
   - Old: Language Models Can Benefit from Domain-Specific Inductive Biases (from title)
   - New: Domain-specific inductive biases and learning strategies can improve language-model efficiency and generalization beyond one general-purpose architecture across all pretraining domains.

16. **Position: Make Planning Research Rigorous Again!** (`xed22c379c5f0`)
   - Old: This rigor should be applied to the current trend of work on planning with large language models.
   - New: LLM planning research should adopt automated planning’s established tools, data, and rigorous evaluation practices instead of repeating known pitfalls.

17. **Position: Current Benchmarking Hinders Real Progress in Deep Learning for Time Series Forecasting** (`2512.22702`)
   - Old: Current benchmarking practices fail to identify the factors responsible for performance differences, thus slowing down progress in the field.
   - New: Time-series benchmarks should isolate foundational design choices and report them explicitly rather than attributing performance differences to architectures alone.

18. **Medical AI Must Be an AI Colleague, Not an Oracle** (`xb31bb1257e92`)
   - Old: Explainability must be a certification requirement for diagnostic AI, alongside accuracy, because current liability rules influence practitioner behavior towards AIS.
   - New: Explainability should be a certification requirement for diagnostic AI because opaque systems distort liability and encourage defensive agreement rather than responsible clinical judgment.

19. **Understanding Generalization Requires Universal Induction** (`2609.34458`)
   - Old: Classical statistical theory is insufficient to explain the successes of general-purpose AI models, because it depends on handcrafted inductive biases that it cannot justify.
   - New: Generalization theory should use universal induction relativized to accessible background information because predictive performance necessarily depends on inductive bias beyond data.

20. **A Sustainable AI Economy Needs Data Deals That Work for Generators** (`2601.09966`)
   - Old: The machine learning value chain is structurally unsustainable due to an economic data processing inequality: each state in the data cycle from inputs to model weights to synthetic outputs refines technical signal but strips economic equity from data generators.
   - New: Sustainable AI requires equitable data markets with provenance, balanced bargaining power, and dynamic pricing that return value to data generators.

### Reproduce the v3 outputs

```bash
.venv/bin/python scripts/build_dataset.py
.venv/bin/python scripts/stats.py
.venv/bin/python scripts/build_readme.py
.venv/bin/python scripts/curation_report.py
```

The v2 baseline is a local, git-ignored snapshot at `.cache/papers_v2.csv`; without it, the before/after comparison cannot be reproduced on a fresh clone. Curated judgments remain drafts and have not yet undergone the separate inclusion-filtering pass in `BACKLOG.md`.
