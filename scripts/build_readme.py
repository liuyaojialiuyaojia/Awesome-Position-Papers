"""Generate README.md and README_zh.md from data/papers.csv + data/stats.json.

The paper tables are never hand-edited: change the data (or data/taxonomy.yaml)
and rerun this script. Framing text lives in the two templates below so the
prose stays reviewable as code.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402
import tag_topics  # noqa: E402

LICENSE_BADGE = ("![license: CC BY 4.0](https://img.shields.io/badge/license-"
                 "CC%20BY%204.0-lightgrey)")

# Xiaohongshu-ish section marks for the Chinese README.
ZH_EMOJI = {
    "Evaluation & benchmarks": "📏", "Agents & autonomy": "🤖",
    "Safety & alignment": "🛟", "Governance & policy": "⚖️",
    "AI for science": "🔬", "Research & open science": "📚",
    "Data & compute": "🗂️", "Models, reasoning & theory": "🧠",
    "People & society": "🙋", "Multimodal & generative media": "🎨",
}

RERUN = """python -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/collect_icml.py --year 2024
.venv/bin/python scripts/collect_icml.py --year 2025
.venv/bin/python scripts/collect_icml.py --year 2026
.venv/bin/python scripts/collect_neurips.py --year 2025
.venv/bin/python scripts/collect_neurips.py --year 2026
.venv/bin/python scripts/collect_arxiv.py
.venv/bin/python scripts/compress_taxonomy.py
.venv/bin/python scripts/build_dataset.py
.venv/bin/python scripts/stats.py
.venv/bin/python scripts/build_readme.py"""


def years_of(per_year: dict, venue: str) -> list[int]:
    """Years the data actually holds for one venue, oldest first."""
    return sorted(int(y) for y in (per_year.get(venue) or {}))


def coverage_en(stats) -> str:
    """The coverage sentence, built from the venue/year counts in the data."""
    py = stats["per_venue_year"]
    parts = []
    for venue in ("ICML", "NeurIPS"):
        years = years_of(py, venue)
        if years:
            parts.append(f"the {venue} Position Paper Track ({', '.join(map(str, years))})")
    parts.append("arXiv titles starting with `Position:` / `Position Paper:` "
                 "(Jan 2023 to today)")
    if len(parts) > 2:
        return "It covers " + ", ".join(parts[:-1]) + ", and " + parts[-1] + "."
    return "It covers " + " and ".join(parts) + "."


def coverage_zh(stats) -> str:
    py = stats["per_venue_year"]
    bits = [f"**{v} {'/'.join(str(y) for y in years_of(py, v))}** 的立场论文赛道"
            for v in ("ICML", "NeurIPS") if years_of(py, v)]
    bits.append("arXiv 标题扫描（2023-01 至今）")
    return " + ".join(bits)


def gh_anchor(heading: str) -> str:
    """Mimic GitHub's slug for an auto-generated heading anchor."""
    s = heading.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE)
    return re.sub(r"\s", "-", s).strip("-")


def cell(text: str) -> str:
    """Escape a CSV value for a Markdown table cell."""
    s = str(text or "").replace("|", "\\|").replace("[", "(").replace("]", ")")
    s = s.replace("`", "'").replace("<", "&lt;").replace(">", "")
    return re.sub(r"\s+", " ", s).strip()


def link(title: str, url: str) -> str:
    return f"[{cell(title)}]({url})" if url else cell(title)


def paper_url(row: dict) -> str:
    return row.get("url") or (f"https://arxiv.org/abs/{row['arxiv_id']}"
                              if row.get("arxiv_id") else "")


def venue_label(row: dict) -> str:
    venue = "arXiv" if (row.get("venue") or "") == "arXiv-only" else (row.get("venue") or "arXiv")
    return f"{venue} · {row.get('year')}" if row.get("year") else venue


def grouped(rows: list[dict], order: list[str]) -> list[tuple[str, list[dict]]]:
    by_topic: dict[str, list[dict]] = {}
    for r in rows:
        by_topic.setdefault(r["topic"], []).append(r)
    out = []
    for label in order:
        group = by_topic.get(label, [])
        if not group:
            continue
        # Newest first, then alphabetically.
        group.sort(key=lambda r: (-int(r["year"]), str(r["title"]).lower()))
        out.append((label, group))
    return out


def sections_en(placed: list[tuple[str, list[dict]]]) -> tuple[str, str]:
    body, toc = [], []
    for label, group in placed:
        heading = f"{label} ({len(group)} papers)"
        toc.append(f"- [{heading}](#{gh_anchor(heading)})")
        body.append(f"### {heading}\n")
        body.append("| Paper | Venue / Year | Stance (draft) |")
        body.append("|---|---|---|")
        for r in group:
            body.append(f"| {link(r['title'], paper_url(r))} | {venue_label(r)} "
                        f"| {cell(r.get('stance_summary'))} |")
        body.append("")
    return "\n".join(body), "\n".join(toc)


def sections_zh(placed: list[tuple[str, list[dict]]], zh_by_label: dict[str, str]) -> tuple[str, str]:
    body, toc = [], []
    for label, group in placed:
        zh = zh_by_label.get(label, label)
        heading = f"{ZH_EMOJI.get(label, '🔹')} {zh}（{len(group)} 篇）"
        toc.append(f"- [{heading}](#{gh_anchor(heading)})")
        body.append(f"### {heading}\n")
        body.append("| 论文 | 出处 | 一句话立场（草稿） |")
        body.append("|---|---|---|")
        for r in group:
            body.append(f"| {link(r['title'], paper_url(r))} | {venue_label(r)} "
                        f"| {cell(r.get('stance_summary'))} |")
        body.append("")
    return "\n".join(body), "\n".join(toc)


def table(pairs: list[tuple[str, int]], head: tuple[str, str], total: int | None = None) -> str:
    lines = [f"| {head[0]} | {head[1]} |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in sorted(pairs, key=lambda kv: -kv[1])]
    if total is not None:
        lines.append(f"| **total (deduplicated)** | **{total}** |")
    return "\n".join(lines)


def venue_year_table(stats) -> str:
    """Venue x year counts, so the coverage sentence above can be checked."""
    py = stats["per_venue_year"]
    years = sorted({y for d in py.values() for y in d}, key=int)
    order = [v for v in ("ICML", "NeurIPS", "arXiv-only") if v in py]
    order += sorted(set(py) - set(order))
    head = "| Venue | " + " | ".join(years) + " | total |"
    lines = [head, "|---" * (len(years) + 2) + "|"]
    for venue in order:
        cells = [str(py[venue].get(y, 0) or "–") for y in years]
        lines.append(f"| {venue} | " + " | ".join(cells) +
                     f" | **{sum(py[venue].values())}** |")
    lines.append("| **total** | " +
                 " | ".join(f"**{sum(py[v].get(y, 0) for v in order)}**" for y in years) +
                 f" | **{stats['papers']}** |")
    return "\n".join(lines)


def charts_md(stats: dict, indent: str = "") -> str:
    out = []
    for c in stats["charts"]:
        alt = os.path.basename(c).replace(".png", "").replace("_", " ")
        out.append(f"![{alt}]({c})")
    return "\n".join(indent + line for line in out)


def build_en(rows, stats, tax) -> str:
    order = [spec["label"] for spec in tax["topics"].values()]
    placed = grouped(rows, sorted(order, key=lambda l: -stats["per_topic"].get(l, 0)))
    body, toc = sections_en(placed)
    updated = stats["generated_at"]

    return f"""# Awesome Position Papers

A curated, data-backed map of **position papers in AI/ML** — papers that argue a
stance instead of proposing a method. {coverage_en(stats)}

![papers: {stats['papers']}](https://img.shields.io/badge/papers-{stats['papers']}-blue)
![topics: {stats['topics']}](https://img.shields.io/badge/topics-{stats['topics']}-blueviolet)
![last update: {updated}](https://img.shields.io/badge/last%20update-{updated.replace('-', '--')}-green)
{LICENSE_BADGE}
![PRs: welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

**{stats['papers']} papers · {stats['topics']} topics · {stats['years']['min']}–{stats['years']['max']}**
· generated from [`data/papers.csv`](data/papers.csv) by [`scripts/`](scripts), so
every number above can be recomputed.

## Why position papers?

Most of a literature map is methods: architectures, objectives, benchmarks.
Position papers do a different job — they take a stance on how the field
*should* think, measure, build, regulate or organise itself. "Evaluation scores
are perishable knowledge", "You can't manufacture a NeRF", "The AI conference
peer review crisis demands author feedback" — these are arguments, not results,
and they are where the community is arguing with itself.

They are also scattered: several conference position tracks plus an arXiv
firehose, with no index. This repo collapses them into one deduplicated table
(a paper that exists both on arXiv and at a venue is a single row), tagged by
topic and re-collectable with the commands at the bottom.

## Contents

{toc}

## How much is there

{table(stats['per_source'].items(), ('Collector', 'papers'), stats['papers'])}

{venue_year_table(stats)}

## Overview

{charts_md(stats)}

> **Stance summaries and topics were written by Kimi-K3.1-Pro (via Qoder CLI)**
> from the abstracts. They are drafts, not ground truth; corrections are welcome
> by PR — see [`CONTRIBUTING.md`](CONTRIBUTING.md). The curated text lives in
> [`data/curated/stances.jsonl`](data/curated/stances.jsonl); papers added later
> without a curated row keep automatic drafts from
> [`data/taxonomy.yaml`](data/taxonomy.yaml) and the extractive stance fallback.

## Papers by topic

{body}
## How this is built

Four collectors, one merge, two charts, two READMEs — all in
[`scripts/`](scripts), all polite to the APIs (descriptive `User-Agent`, ≥3 s
between requests, exponential back-off on `429`, raw responses cached under
`.cache/`, which is git-ignored):

| Script | What it does |
|---|---|
| `scripts/collect_icml.py --year 2024\\|2025\\|2026` | ICML position track: the virtual-site export for 2024-25, and for 2026 the track page plus one page per paper for its abstract |
| `scripts/collect_neurips.py --year 2025\\|2026` | NeurIPS position track: the track page joined to the virtual-site export; 2026 unions the three locale sites |
| `scripts/collect_arxiv.py` | arXiv titles starting with `Position:` / `Position Paper:` (Jan 2023 → today) |
| `scripts/link_arxiv.py` | resolves arXiv ids for venue papers the title scan missed |
| `scripts/build_dataset.py` | merge + dedupe + curated stance/topic overrides + confirmed exclusions → `data/papers.csv` |
| `scripts/filter_candidates.py` | flags possible duplicates, withdrawals, short abstracts, and non-position papers for review |
| `scripts/compress_taxonomy.py` | applies the explicit legacy-topic mapping to curated rows |
| `scripts/tag_topics.py` | automatic topic and stance fallbacks for papers without curated rows |
| `scripts/stats.py` | `data/stats.json` and the two charts |
| `scripts/stance_report.py` | stance-quality counts and before/after pairs for `REPORT.md` |
| `scripts/build_readme.py` | regenerates `README.md` and `README_zh.md` |

Rerun everything from scratch:

```bash
{RERUN}
```

Second runs are near-instant because every raw response is cached.

## Contributing

Missing paper, wrong topic, better one-liner, another venue: see
[`CONTRIBUTING.md`](CONTRIBUTING.md). Please do not hand-edit the tables — edit
the data or the scripts and regenerate them.

## Citation

The dataset and the text are **CC BY 4.0** (see [`LICENSE`](LICENSE)); the
papers themselves belong to their authors.

```bibtex
@misc{{awesome_position_papers,
  title         = {{Awesome Position Papers: a data-backed map of AI/ML position papers}},
  author        = {{Awesome Position Papers contributors}},
  year          = {{2026}},
  howpublished  = {{GitHub repository: awesome-position-papers}},
  note          = {{{stats['papers']} papers, generated from collected metadata, CC BY 4.0}}
}}
```

Collection caveats — blocked APIs, the per-year rule used to recognise the
track, and known gaps — are documented in [`REPORT.md`](REPORT.md).
"""


def build_zh(rows, stats, tax) -> str:
    zh_by_label = {spec["label"]: spec.get("label_zh", spec["label"])
                   for spec in tax["topics"].values()}
    order = list(zh_by_label)
    placed = grouped(rows, sorted(order, key=lambda l: -stats["per_topic"].get(l, 0)))
    body, toc = sections_zh(placed, zh_by_label)
    updated = stats["generated_at"]
    src = "\n".join(f"- `{k}` → **{v} 篇**"
                    for k, v in sorted(stats["per_source"].items(), key=lambda kv: -kv[1]))
    years = " · ".join(f"{y}：{n}" for y, n in sorted(stats["per_year"].items()))

    return f"""# Awesome Position Papers 🧭 AI 立场论文全景图

> 只讲观点、不讲方法的论文，到底有多少？都吵些什么话题？
> 我们把 {coverage_zh(stats)} 全扒了一遍，做成可复现的数据集。

![papers: {stats['papers']}](https://img.shields.io/badge/papers-{stats['papers']}-blue)
![topics: {stats['topics']}](https://img.shields.io/badge/topics-{stats['topics']}-blueviolet)
![updated: {updated}](https://img.shields.io/badge/last%20update-{updated.replace('-', '--')}-green)
{LICENSE_BADGE}
![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

**{stats['papers']} 篇论文 · {stats['topics']} 个主题 · {stats['years']['min']}–{stats['years']['max']} 年**
全部由脚本抓取、去重、打标签，**数字可复算，表格可重跑**。

## ✨ 为什么是立场论文

- 普通论文讲「怎么做」，立场论文讲「**该不该这么做**」
- 它们是社区争论的前线：评测算不算数、开源要不要管、算力要不要省、同行评审怎么改
- 但它们散落在几个会议的立场论文赛道 + arXiv 洪水里，**根本追不过来**
- 于是我们把它们收进同一张表，arXiv 和会议重复的只留一行 📄

## 📊 盘子有多大

{src}

去重后合计：**{stats['papers']} 篇**

{years}

{venue_year_table(stats)}

## 🖼️ 一图看懂

{charts_md(stats)}

## 🏷️ 目录

{toc}

## 📚 分主题看（共 {stats['topics']} 个主题）

> ⚠️ `主题` 和 `一句话立场` 由 **Kimi-K3.1-Pro（通过 Qoder CLI）** 阅读摘要后撰写，
> 仍是草稿，不是标准答案；发现不准，**欢迎 PR 修正**，详见
> [`CONTRIBUTING.md`](CONTRIBUTING.md)。精选文本保存在
> [`data/curated/stances.jsonl`](data/curated/stances.jsonl)；以后新增但尚未精选的论文，
> 保留关键词主题与抽取式立场的自动草稿。论文标题与立场保留英文，避免二次失真。

{body}
---

## 🔁 怎么复现

```bash
{RERUN}
```

原始返回都缓存在 `.cache/`（已 gitignore），第二次跑几乎秒出 ⚡

## 🙌 想加论文

- 缺少论文：加一个 collector，或按贡献指南补数据
- 主题或立场不准：修改 `data/curated/stances.jsonl` 中对应 ID，再重建
- 规矩写在 [`CONTRIBUTING.md`](CONTRIBUTING.md)

## 📌 引用

数据与文字用 **CC BY 4.0**（见 [`LICENSE`](LICENSE)），论文版权归论文作者。

```bibtex
@misc{{awesome_position_papers,
  title         = {{Awesome Position Papers: a data-backed map of AI/ML position papers}},
  author        = {{Awesome Position Papers contributors}},
  year          = {{2026}},
  howpublished  = {{GitHub repository: awesome-position-papers}},
  note          = {{{stats['papers']} papers, CC BY 4.0}}
}}
```

> 📄 抓取的坑（哪个 API 被墙、每年怎么认出这个赛道、已知缺口）都写在
> [`REPORT.md`](REPORT.md)。
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=os.path.join(C.DATA, "papers.csv"))
    ap.add_argument("--stats", default=os.path.join(C.DATA, "stats.json"))
    args = ap.parse_args()

    rows = [r for r in C.read_csv(args.csv) if r.get("excluded", "").lower() != "true"]
    with open(args.stats, encoding="utf-8") as fh:
        stats = json.load(fh)
    tax = tag_topics.load_taxonomy()

    for lang, text in (("en", build_en(rows, stats, tax)), ("zh", build_zh(rows, stats, tax))):
        path = os.path.join(C.REPO, "README.md" if lang == "en" else "README_zh.md")
        marker = ("<!-- Generated by scripts/build_readme.py from data/papers.csv and "
                  "data/stats.json.\n     Edit the data or the scripts and rerun; "
                  "do not hand-edit the tables. -->\n\n")
        body = re.sub(r"\n{4,}", "\n\n\n", marker + text)
        if not body.endswith("\n"):
            body += "\n"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        print(f"  wrote {os.path.relpath(path, C.REPO)} "
              f"({len(body.splitlines())} lines, {len(rows)} papers)")


if __name__ == "__main__":
    main()
