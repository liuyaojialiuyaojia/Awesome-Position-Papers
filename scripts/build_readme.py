"""Generate concise English and Chinese reading guides from the curated data."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402
import tag_topics  # noqa: E402

LICENSE_BADGE = ("![license: CC BY 4.0](https://img.shields.io/badge/license-"
                 "CC%20BY%204.0-lightgrey)")

ZH_EMOJI = {
    "Evaluation & benchmarks": "📏", "Agents & autonomy": "🤖",
    "Safety & alignment": "🛟", "Governance & policy": "⚖️",
    "AI for science": "🔬", "Research & open science": "📚",
    "Data & compute": "🗂️", "Models, reasoning & theory": "🧠",
    "People & society": "🙋", "Multimodal & generative media": "🎨",
}


def load_yaml(path: str) -> dict:
    """Parse the nested mappings and lists used by the curated YAML files."""
    tokens = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip() and not line.lstrip().startswith("#"):
                tokens.append((len(line) - len(line.lstrip(" ")), line.strip()))

    def scalar(text: str):
        if text.startswith('"') and text.endswith('"'):
            return json.loads(text)
        if text.startswith("'") and text.endswith("'"):
            return text[1:-1].replace("''", "'")
        return text

    def mapping(i: int, indent: int) -> tuple[dict, int]:
        node = {}
        while i < len(tokens) and tokens[i][0] == indent and not tokens[i][1].startswith("- "):
            key, _, rest = tokens[i][1].partition(":")
            i += 1
            if rest.strip():
                node[key.strip()] = scalar(rest.strip())
            elif i < len(tokens) and tokens[i][0] > indent:
                node[key.strip()], i = block(i, tokens[i][0])
            else:
                node[key.strip()] = None
        return node, i

    def block(i: int, indent: int):
        if not tokens[i][1].startswith("- "):
            return mapping(i, indent)
        items = []
        while i < len(tokens) and tokens[i][0] == indent and tokens[i][1].startswith("- "):
            rest = tokens[i][1][2:].strip()
            i += 1
            if ":" not in rest:
                items.append(scalar(rest))
                continue
            key, _, value = rest.partition(":")
            item = {key.strip(): scalar(value.strip()) if value.strip() else None}
            if i < len(tokens) and tokens[i][0] > indent:
                extra, i = mapping(i, tokens[i][0])
                item.update(extra)
            items.append(item)
        return items, i

    value, _ = block(0, tokens[0][0])
    return value


def md_text(text: str) -> str:
    text = re.sub(r"\s+", " ", str(text or "")).strip()
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def paper_url(row: dict) -> str:
    return row.get("url") or (f"https://arxiv.org/abs/{row['arxiv_id']}"
                              if row.get("arxiv_id") else "")


def paper_link(row: dict) -> str:
    title = md_text(row["title"])
    url = paper_url(row)
    return f"[{title}]({url})" if url else title


def year_span(stats: dict, venue: str) -> str:
    years = sorted(int(y) for y in stats["per_venue_year"].get(venue, {}))
    if not years:
        return ""
    if len(years) == years[-1] - years[0] + 1:
        return str(years[0]) if len(years) == 1 else f"{years[0]}–{years[-1]}"
    return ", ".join(map(str, years))


def chart_path(stats: dict) -> str:
    return next(c for c in stats["charts"] if "by_year" in c)


def essential_sections(rows_by_id: dict, essentials: dict, tax: dict,
                       chinese: bool = False) -> str:
    grouped = {}
    for item in essentials["papers"]:
        row = rows_by_id[item["id"]]
        grouped.setdefault(row["topic"], []).append((row, item["why"]))

    labels = {spec["label"]: spec.get("label_zh", spec["label"])
              for spec in tax["topics"].values()}
    lines = []
    for spec in tax["topics"].values():
        topic = spec["label"]
        if topic not in grouped:
            continue
        heading = labels[topic] if chinese else topic
        prefix = f"{ZH_EMOJI.get(topic, '🔹')} " if chinese else ""
        lines.extend([f"### {prefix}{heading}", ""])
        for row, why in grouped[topic]:
            lines.append(f"- {paper_link(row)} — {md_text(why)}")
        lines.append("")
    return "\n".join(lines).strip()


def debate_cards(rows_by_id: dict, debates: dict) -> str:
    cards = []
    for debate in debates["debates"]:
        cards.extend([
            "<details>",
            f"<summary>⚖️ <strong>{html.escape(debate['question'])}</strong></summary>",
            "",
        ])
        for paper in debate["papers"]:
            row = rows_by_id[paper["id"]]
            cards.append(f"- {paper_link(row)} — {md_text(paper['side'])}")
        cards.extend(["", "</details>", ""])
    return "\n".join(cards).strip()


def bibtex(papers: int) -> str:
    return f"""```bibtex
@misc{{awesome_position_papers,
  title        = {{Awesome Position Papers: A Data-Backed Map of AI/ML Position Papers}},
  author       = {{Awesome Position Papers contributors}},
  year         = {{2026}},
  howpublished = {{GitHub repository: awesome-position-papers}},
  note         = {{{papers} papers, CC BY 4.0}}
}}
```"""


def build_en(rows_by_id: dict, stats: dict, tax: dict,
             essentials: dict, debates: dict) -> str:
    essential_count = len(essentials["papers"])
    debate_count = len(debates["debates"])
    return f"""# Awesome Position Papers

A curated guide to AI/ML papers that argue what the field should believe, measure, build, or regulate.

![papers: {stats['papers']}](https://img.shields.io/badge/papers-{stats['papers']}-blue)
![last update: {stats['generated_at']}](https://img.shields.io/badge/last%20update-{stats['generated_at'].replace('-', '--')}-green)
{LICENSE_BADGE}
![PRs: welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

**{stats['papers']} papers · {stats['topics']} topics · {stats['years']['min']}–{stats['years']['max']}**

Coverage: **ICML {year_span(stats, 'ICML')}** and **NeurIPS {year_span(stats, 'NeurIPS')}** position tracks, plus arXiv titles beginning `Position:`.

## At a glance

![Papers per topic by year]({chart_path(stats)})

## Essential reads

{essential_count} abstract-level selections, grouped by topic; each note explains why the paper matters. Stance summaries and topics were written by **Kimi-K3.1-Pro (via Qoder CLI)** from the abstracts. All are drafts—[corrections are welcome](CONTRIBUTING.md).

{essential_sections(rows_by_id, essentials, tax)}

## Hot debates

{debate_count} concrete questions with genuinely different answers. Expand a card to compare the linked papers; sides are editorial summaries, not direct replies between authors.

{debate_cards(rows_by_id, debates)}

## Full paper list

[Open the searchable website](docs/index.html) for all {stats['papers']} papers, with topic/venue/year filters and citation sorting.

## How it is built

- `collect_*.py` gathers public metadata; `build_dataset.py` deduplicates it and applies curated topics, stances, and exclusions.
- `fetch_citations.py` records dated OpenAlex counts; `stats.py` computes every number and chart; `build_readme.py` generates both guides.
- Rebuild in order: `build_dataset.py`, `fetch_citations.py`, `stats.py`, `build_readme.py`, `build_site.py`; run each as `.venv/bin/python scripts/<script>`.

## Citation

Dataset and text: **CC BY 4.0** ([license](LICENSE)). Papers remain their authors’ work.

{bibtex(stats['papers'])}
"""


def build_zh(rows_by_id: dict, stats: dict, tax: dict,
             essentials: dict, debates: dict) -> str:
    essential_count = len(essentials["papers"])
    debate_count = len(debates["debates"])
    return f"""# 🧭 Awesome Position Papers

AI 论文不只有「怎么做」，还有「该不该」。这里把散落的立场论文整理成一份能直接开读的指南。

![papers: {stats['papers']}](https://img.shields.io/badge/papers-{stats['papers']}-blue)
![updated: {stats['generated_at']}](https://img.shields.io/badge/last%20update-{stats['generated_at'].replace('-', '--')}-green)
{LICENSE_BADGE}
![PRs welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)

**{stats['papers']} 篇论文 · {stats['topics']} 个主题 · {stats['years']['min']}–{stats['years']['max']} 年**

收录 **ICML {year_span(stats, 'ICML')}**、**NeurIPS {year_span(stats, 'NeurIPS')}** 立场论文赛道，以及标题以 `Position:` 开头的 arXiv 论文。

## 📊 一图看分布

![各主题论文数量：按年份拆分]({chart_path(stats)})

## ⭐ 先读这些

按主题精选 {essential_count} 篇，每篇一句「为什么值得读」。主题与立场由 **Kimi-K3.1-Pro（通过 Qoder CLI）** 阅读摘要后撰写，仍是草稿；论文标题和导读保留英文，[欢迎 PR 修正](CONTRIBUTING.md)。

{essential_sections(rows_by_id, essentials, tax, chinese=True)}

## ⚖️ 热门争论

{debate_count} 个具体问题，不同论文给出不同答案。点开卡片对照双方；这里只做摘要级整理，不代表作者直接互相回应。

{debate_cards(rows_by_id, debates)}

## 🔎 查完整论文库

[打开可搜索网站](docs/index.html)，按主题、会议和年份筛选全部 {stats['papers']} 篇论文，也可按引用数排序。

## 🛠️ 怎么构建

- `collect_*.py` 收集公开元数据，`build_dataset.py` 去重，并应用精选主题、立场与排除记录。
- `fetch_citations.py` 记录带日期的 OpenAlex 引用数，`stats.py` 计算所有数字和图表，`build_readme.py` 生成中英文指南。
- 依次重建：`build_dataset.py`、`fetch_citations.py`、`stats.py`、`build_readme.py`、`build_site.py`；均用 `.venv/bin/python scripts/<脚本名>` 运行。

## 📌 怎么引用

数据与文字采用 **CC BY 4.0**（见 [LICENSE](LICENSE)）；论文版权归论文作者。

{bibtex(stats['papers'])}
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=os.path.join(C.DATA, "papers.csv"))
    ap.add_argument("--stats", default=os.path.join(C.DATA, "stats.json"))
    args = ap.parse_args()

    rows = [r for r in C.read_csv(args.csv) if r.get("excluded", "").lower() != "true"]
    rows_by_id = {r["id"]: r for r in rows}
    with open(args.stats, encoding="utf-8") as fh:
        stats = json.load(fh)
    tax = tag_topics.load_taxonomy()
    essentials = load_yaml(os.path.join(C.DATA, "curated", "essentials.yaml"))
    debates = load_yaml(os.path.join(C.DATA, "curated", "debates.yaml"))

    curated_ids = [p["id"] for p in essentials["papers"]]
    curated_ids += [p["id"] for d in debates["debates"] for p in d["papers"]]
    missing = sorted(set(curated_ids) - set(rows_by_id))
    if missing:
        raise ValueError(f"Curated README ids missing from public CSV: {', '.join(missing)}")

    for lang, text in (
        ("en", build_en(rows_by_id, stats, tax, essentials, debates)),
        ("zh", build_zh(rows_by_id, stats, tax, essentials, debates)),
    ):
        path = os.path.join(C.REPO, "README.md" if lang == "en" else "README_zh.md")
        marker = ("<!-- Generated by scripts/build_readme.py from data/papers.csv, "
                  "data/stats.json, and data/curated/.\n     Edit the data or scripts "
                  "and rerun; do not hand-edit. -->\n\n")
        body = re.sub(r"\n{4,}", "\n\n\n", marker + text)
        if not body.endswith("\n"):
            body += "\n"
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        print(f"  wrote {os.path.relpath(path, C.REPO)} ({len(body.splitlines())} lines, "
              f"{len(essentials['papers'])} essentials, {len(debates['debates'])} debates)")


if __name__ == "__main__":
    main()
