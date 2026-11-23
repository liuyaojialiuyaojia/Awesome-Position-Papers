"""Generate the self-contained GitHub Pages reading interface in docs/."""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402
from build_readme import load_yaml  # noqa: E402


HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Search and compare AI/ML position papers by topic, venue, and year.">
  <meta name="theme-color" content="#f6f7f4">
  <title>Awesome Position Papers</title>
  <script>
    (function () {
      var saved = null;
      try { saved = localStorage.getItem("position-papers-theme"); } catch (error) {}
      var dark = window.matchMedia("(prefers-color-scheme: dark)").matches;
      document.documentElement.dataset.theme = saved === "light" || saved === "dark" ? saved : (dark ? "dark" : "light");
    }());
  </script>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f4;
      --surface: #ffffff;
      --ink: #19231f;
      --muted: #59665f;
      --line: #dce2dd;
      --accent: #196149;
      --accent-soft: #e5f1eb;
      --on-accent: #ffffff;
      --shadow: 0 8px 28px rgba(25, 35, 31, 0.05);
    }
    :root[data-theme="dark"] {
      color-scheme: dark;
      --bg: #111713;
      --surface: #18201b;
      --ink: #edf3ef;
      --muted: #abb8b0;
      --line: #334139;
      --accent: #8dd3b3;
      --accent-soft: #223c30;
      --on-accent: #10251b;
      --shadow: none;
    }
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.55;
      -webkit-font-smoothing: antialiased;
    }
    button, input, select { font: inherit; }
    button, summary, select { cursor: pointer; }
    a { color: var(--accent); text-decoration-thickness: 1px; text-underline-offset: 3px; }
    a:hover { text-decoration-thickness: 2px; }
    button:focus-visible, a:focus-visible, input:focus-visible, select:focus-visible, summary:focus-visible {
      outline: 3px solid var(--accent);
      outline-offset: 3px;
    }
    [hidden] { display: none !important; }
    .container { width: min(1120px, calc(100% - 40px)); margin-inline: auto; }
    .sr-only {
      position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px;
      overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0;
    }
    .skip-link { position: fixed; top: 8px; left: 8px; z-index: 10; padding: 10px 14px; background: var(--surface); transform: translateY(-150%); }
    .skip-link:focus { transform: translateY(0); }
    .site-header { border-bottom: 1px solid var(--line); background: var(--surface); }
    .header-inner { min-height: 72px; display: flex; align-items: center; justify-content: space-between; gap: 20px; }
    .brand { color: var(--ink); font-weight: 750; text-decoration: none; letter-spacing: -0.02em; }
    .header-actions, .view-nav { display: flex; align-items: center; gap: 8px; }
    .view-nav { padding: 4px; border: 1px solid var(--line); border-radius: 12px; }
    .view-button, .theme-button, .clear-button, .more-button {
      min-height: 40px; border: 1px solid transparent; border-radius: 8px; padding: 7px 13px;
      background: transparent; color: var(--muted); font-weight: 650;
    }
    .view-button[aria-pressed="true"] { background: var(--accent-soft); color: var(--accent); }
    .theme-button, .clear-button { border-color: var(--line); }
    .theme-button:hover, .clear-button:hover, .view-button:hover { color: var(--accent); }
    .hero { max-width: 790px; padding: 58px 0 34px; }
    .kicker { margin: 0 0 12px; color: var(--accent); font-size: 0.78rem; font-weight: 750; letter-spacing: 0.12em; text-transform: uppercase; }
    h1 { margin: 0; font-size: clamp(2.25rem, 6vw, 4rem); line-height: 1.06; letter-spacing: -0.045em; }
    .lede { max-width: 690px; margin: 20px 0 0; color: var(--muted); font-size: 1.08rem; }
    .key-numbers { display: flex; flex-wrap: wrap; gap: 8px 22px; margin: 24px 0 0; padding: 0; list-style: none; font-size: 0.94rem; font-weight: 650; }
    .controls { padding: 22px; border: 1px solid var(--line); border-radius: 16px; background: var(--surface); box-shadow: var(--shadow); }
    .control-top { display: grid; grid-template-columns: minmax(0, 1fr) 220px; gap: 16px; }
    .control-label { display: block; margin-bottom: 7px; font-size: 0.83rem; font-weight: 700; }
    .search-input, .sort-select {
      width: 100%; min-height: 46px; border: 1px solid var(--line); border-radius: 10px;
      padding: 10px 12px; background: var(--bg); color: var(--ink);
    }
    .search-input::placeholder { color: var(--muted); opacity: 0.85; }
    .filter-groups { display: grid; gap: 16px; margin-top: 20px; padding-top: 18px; border-top: 1px solid var(--line); }
    fieldset { min-width: 0; margin: 0; padding: 0; border: 0; }
    legend { margin-bottom: 8px; padding: 0; color: var(--muted); font-size: 0.78rem; font-weight: 750; text-transform: uppercase; letter-spacing: 0.06em; }
    .chips { display: flex; flex-wrap: wrap; gap: 7px; }
    .chip {
      min-height: 36px; padding: 6px 12px; border: 1px solid var(--line); border-radius: 999px;
      background: transparent; color: var(--muted); font-size: 0.86rem;
    }
    .chip:hover { border-color: var(--accent); color: var(--accent); }
    .chip[aria-pressed="true"] { border-color: var(--accent); background: var(--accent); color: var(--on-accent); font-weight: 650; }
    .filter-footer { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 18px; }
    .essential-control { display: inline-flex; align-items: center; gap: 9px; min-height: 40px; font-size: 0.9rem; font-weight: 650; cursor: pointer; }
    .essential-control input { width: 18px; height: 18px; margin: 0; accent-color: var(--accent); }
    .clear-button { min-height: 36px; padding-block: 5px; font-size: 0.84rem; }
    .results-bar { display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 26px 0 14px; }
    .result-count { margin: 0; font-weight: 700; }
    .draft-note { margin: 0; color: var(--muted); font-size: 0.82rem; }
    .paper-list { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
    .paper-card { min-width: 0; padding: 22px; border: 1px solid var(--line); border-radius: 14px; background: var(--surface); }
    .paper-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; margin-bottom: 12px; color: var(--muted); font-size: 0.79rem; }
    .topic-label { color: var(--accent); font-weight: 700; }
    .essential-badge { padding: 2px 7px; border-radius: 999px; background: var(--accent-soft); color: var(--accent); font-weight: 750; }
    .paper-card h2 { margin: 0; font-size: 1.08rem; line-height: 1.4; letter-spacing: -0.012em; overflow-wrap: anywhere; }
    .paper-card h2 a { color: var(--ink); text-decoration-color: var(--line); }
    .paper-card h2 a:hover { color: var(--accent); text-decoration-color: var(--accent); }
    .stance { margin: 13px 0 0; }
    .why { margin: 13px 0 0; padding-left: 11px; border-left: 3px solid var(--accent); color: var(--muted); font-size: 0.88rem; }
    .abstract-details { margin-top: 16px; padding-top: 5px; border-top: 1px solid var(--line); }
    .abstract-details summary { min-height: 40px; display: flex; align-items: center; color: var(--accent); font-size: 0.87rem; font-weight: 700; }
    .abstract { margin: 2px 0 5px; color: var(--muted); font-size: 0.91rem; line-height: 1.65; }
    .more-wrap { display: flex; justify-content: center; margin: 26px 0 0; }
    .more-button { min-height: 44px; border-color: var(--accent); color: var(--accent); }
    .more-button:hover { background: var(--accent-soft); }
    .empty-state { margin-top: 20px; padding: 36px 22px; border: 1px dashed var(--line); border-radius: 14px; text-align: center; }
    .empty-state h2 { margin: 0 0 8px; font-size: 1.15rem; }
    .empty-state p { margin: 0; color: var(--muted); }
    .section-heading { margin: 50px 0 22px; }
    .section-heading h2 { margin: 0; font-size: clamp(1.8rem, 4vw, 2.5rem); letter-spacing: -0.03em; }
    .section-heading p { max-width: 700px; margin: 10px 0 0; color: var(--muted); }
    .debate-list { display: grid; gap: 20px; }
    .debate-card { padding: 26px; border: 1px solid var(--line); border-radius: 16px; background: var(--surface); }
    .debate-card h2 { margin: 0; font-size: 1.3rem; line-height: 1.35; letter-spacing: -0.02em; }
    .debate-context { margin: 10px 0 20px; color: var(--muted); }
    .sides { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 12px; }
    .side { min-width: 0; padding: 18px; border-radius: 12px; background: var(--bg); }
    .side h3 { margin: 0 0 10px; font-size: 0.98rem; line-height: 1.4; overflow-wrap: anywhere; }
    .side h3 a { color: var(--ink); }
    .side p { margin: 0; color: var(--muted); font-size: 0.91rem; }
    .side .side-meta { margin-bottom: 7px; color: var(--accent); font-size: 0.76rem; font-weight: 700; }
    .load-error { color: var(--ink); }
    .site-footer { margin-top: 64px; padding: 26px 0 34px; border-top: 1px solid var(--line); color: var(--muted); font-size: 0.82rem; }
    .footer-inner { display: flex; justify-content: space-between; gap: 12px 24px; flex-wrap: wrap; }
    @media (max-width: 720px) {
      .container { width: min(100% - 28px, 1120px); }
      .header-inner { min-height: 66px; gap: 10px; }
      .brand { max-width: 120px; line-height: 1.2; }
      .header-actions { gap: 6px; }
      .view-button, .theme-button { padding-inline: 10px; font-size: 0.85rem; }
      .hero { padding: 38px 0 26px; }
      .control-top, .paper-list { grid-template-columns: 1fr; }
      .controls { padding: 16px; }
      .results-bar { align-items: flex-start; flex-direction: column; gap: 3px; }
      .debate-card { padding: 20px; }
      .sides { grid-template-columns: 1fr; }
      .filter-footer { align-items: flex-start; }
    }
    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
      *, *::before, *::after { transition: none !important; }
    }
  </style>
</head>
<body>
  <a class="skip-link" href="#main">Skip to content</a>
  <header class="site-header">
    <div class="container header-inner">
      <a class="brand" href="./">Awesome Position Papers</a>
      <div class="header-actions">
        <nav class="view-nav" aria-label="Views">
          <button class="view-button" id="papers-view-button" type="button" aria-pressed="true" aria-controls="papers-view">Papers</button>
          <button class="view-button" id="debates-view-button" type="button" aria-pressed="false" aria-controls="debates-view">Debates</button>
        </nav>
        <button class="theme-button" id="theme-button" type="button">Theme</button>
      </div>
    </div>
  </header>

  <main class="container" id="main">
    <section class="hero" aria-labelledby="page-title">
      <p class="kicker">A curated map of AI/ML position papers</p>
      <h1 id="page-title">Position papers, mapped.</h1>
      <p class="lede">Find papers that argue what the field should believe, measure, build, or regulate. Start with the essential reads, or compare opposing answers in the debate map.</p>
      <ul class="key-numbers" aria-label="Collection summary">
        <li>__PAPER_COUNT__ papers</li>
        <li>__ESSENTIAL_COUNT__ essential reads</li>
        <li>__DEBATE_COUNT__ debates</li>
      </ul>
    </section>

    <section id="papers-view" aria-labelledby="papers-heading">
      <h2 class="sr-only" id="papers-heading">Paper browser</h2>
      <div class="controls" aria-label="Search and filter papers">
        <div class="control-top">
          <div>
            <label class="control-label" for="search">Search</label>
            <input class="search-input" id="search" type="search" placeholder="Title, stance, author, or topic" autocomplete="off">
          </div>
          <div>
            <label class="control-label" for="sort">Sort by</label>
            <select class="sort-select" id="sort">
              <option value="newest">Year: newest first</option>
              <option value="oldest">Year: oldest first</option>
              __CITATION_OPTION__
            </select>
          </div>
        </div>
        <div class="filter-groups" id="filter-groups"></div>
        <div class="filter-footer">
          <label class="essential-control" for="essential-only">
            <input id="essential-only" type="checkbox">
            Essential only
          </label>
          <button class="clear-button" id="clear-button" type="button" hidden>Clear filters</button>
        </div>
      </div>
      <div class="results-bar">
        <p class="result-count" id="result-count" role="status" aria-live="polite">Loading papers…</p>
        <p class="draft-note">Stances and topics are abstract-level drafts.__CITATION_NOTE__</p>
      </div>
      <div class="paper-list" id="paper-list" aria-busy="true"></div>
      <div class="empty-state" id="empty-state" hidden>
        <h2>No papers match</h2>
        <p>Try a broader search or clear the filters.</p>
      </div>
      <div class="more-wrap">
        <button class="more-button" id="more-button" type="button" hidden>Show more</button>
      </div>
      <noscript><p class="empty-state">JavaScript is required to search the local paper data. The same records are available in papers.json.</p></noscript>
    </section>

    <section id="debates-view" aria-labelledby="debates-heading" hidden>
      <div class="section-heading">
        <h2 id="debates-heading">Concrete questions, different answers.</h2>
        <p>Each side summarizes an abstract-level claim. These papers address the same question, but are not necessarily direct replies to one another.</p>
      </div>
      <div class="debate-list" id="debate-list"></div>
    </section>
  </main>

  <footer class="site-footer">
    <div class="container footer-inner">
      <span>Data and text: CC BY 4.0. Papers remain their authors’ work.</span>
      <span>Updated __GENERATED_AT__</span>
    </div>
  </footer>

  <script>
    (function () {
      "use strict";

      var PAGE_SIZE = 40;
      var papers = [];
      var filtered = [];
      var visible = PAGE_SIZE;
      var state = { topic: "all", venue: "all", year: "all", query: "", essential: false, sort: "newest" };
      var byId = function (id) { return document.getElementById(id); };

      function element(tag, className, text) {
        var node = document.createElement(tag);
        if (className) { node.className = className; }
        if (text !== undefined) { node.textContent = text; }
        return node;
      }

      function paperLink(paper, heading) {
        var title = element(heading);
        if (paper.url) {
          var link = element("a", "", paper.title);
          link.href = paper.url;
          title.appendChild(link);
        } else {
          title.textContent = paper.title;
        }
        return title;
      }

      function updateThemeButton() {
        var dark = document.documentElement.dataset.theme === "dark";
        var button = byId("theme-button");
        button.textContent = dark ? "Light" : "Dark";
        button.setAttribute("aria-label", "Switch to " + (dark ? "light" : "dark") + " theme");
        button.setAttribute("aria-pressed", String(dark));
        document.querySelector('meta[name="theme-color"]').content = dark ? "#111713" : "#f6f7f4";
      }

      byId("theme-button").addEventListener("click", function () {
        var theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
        document.documentElement.dataset.theme = theme;
        try { localStorage.setItem("position-papers-theme", theme); } catch (error) {}
        updateThemeButton();
      });
      updateThemeButton();

      function setView(view) {
        var papersActive = view === "papers";
        byId("papers-view").hidden = !papersActive;
        byId("debates-view").hidden = papersActive;
        byId("papers-view-button").setAttribute("aria-pressed", String(papersActive));
        byId("debates-view-button").setAttribute("aria-pressed", String(!papersActive));
      }
      byId("papers-view-button").addEventListener("click", function () { setView("papers"); });
      byId("debates-view-button").addEventListener("click", function () { setView("debates"); });

      function buildFilter(group, label, values, allLabel) {
        var fieldset = element("fieldset");
        fieldset.dataset.group = group;
        fieldset.appendChild(element("legend", "", label));
        var chips = element("div", "chips");
        ["all"].concat(values).forEach(function (value) {
          var button = element("button", "chip", value === "all" ? allLabel : value);
          button.type = "button";
          button.dataset.value = value;
          button.setAttribute("aria-pressed", String(state[group] === value));
          button.addEventListener("click", function () {
            state[group] = value;
            fieldset.querySelectorAll(".chip").forEach(function (chip) {
              chip.setAttribute("aria-pressed", String(chip.dataset.value === value));
            });
            applyFilters();
          });
          chips.appendChild(button);
        });
        fieldset.appendChild(chips);
        byId("filter-groups").appendChild(fieldset);
      }

      function buildFilters() {
        var topics = Array.from(new Set(papers.map(function (paper) { return paper.topic; }))).sort();
        var venues = Array.from(new Set(papers.map(function (paper) { return paper.venue; }))).sort();
        var years = Array.from(new Set(papers.map(function (paper) { return String(paper.year); }))).sort().reverse();
        byId("filter-groups").replaceChildren();
        buildFilter("topic", "Topic", topics, "All topics");
        buildFilter("venue", "Venue", venues, "All venues");
        buildFilter("year", "Year", years, "All years");
      }

      function paperCard(paper) {
        var card = element("article", "paper-card");
        var meta = element("div", "paper-meta");
        meta.appendChild(element("span", "topic-label", paper.topic));
        meta.appendChild(element("span", "", paper.venue + " · " + paper.year));
        if (paper.citations !== null) { meta.appendChild(element("span", "", paper.citations + (paper.citations === 1 ? " citation" : " citations"))); }
        if (paper.essential) { meta.appendChild(element("span", "essential-badge", "Essential")); }
        card.appendChild(meta);
        card.appendChild(paperLink(paper, "h2"));
        card.appendChild(element("p", "stance", paper.stance));
        if (paper.why) { card.appendChild(element("p", "why", "Why read it: " + paper.why)); }
        var details = element("details", "abstract-details");
        details.appendChild(element("summary", "", "Read abstract"));
        details.appendChild(element("p", "abstract", paper.abstract));
        card.appendChild(details);
        return card;
      }

      function renderPapers() {
        var list = byId("paper-list");
        var fragment = document.createDocumentFragment();
        filtered.slice(0, visible).forEach(function (paper) { fragment.appendChild(paperCard(paper)); });
        list.replaceChildren(fragment);
        var count = filtered.length;
        byId("result-count").textContent = count + (count === 1 ? " paper" : " papers") + (count > visible ? " · showing " + visible : "");
        byId("empty-state").hidden = count !== 0;
        var remaining = Math.max(0, count - visible);
        byId("more-button").hidden = remaining === 0;
        byId("more-button").textContent = remaining ? "Show more (" + remaining + " remaining)" : "Show more";
        var active = state.topic !== "all" || state.venue !== "all" || state.year !== "all" || state.query || state.essential;
        byId("clear-button").hidden = !active;
      }

      function applyFilters() {
        var terms = state.query.split(/\s+/).filter(Boolean);
        filtered = papers.filter(function (paper) {
          return (state.topic === "all" || paper.topic === state.topic) &&
            (state.venue === "all" || paper.venue === state.venue) &&
            (state.year === "all" || String(paper.year) === state.year) &&
            (!state.essential || paper.essential) &&
            terms.every(function (term) { return paper.searchText.includes(term); });
        });
        filtered.sort(function (a, b) {
          if (state.sort === "oldest") { return a.year - b.year || a.title.localeCompare(b.title); }
          if (state.sort === "citations") {
            return (b.citations === null ? -1 : b.citations) - (a.citations === null ? -1 : a.citations) ||
              b.year - a.year || a.title.localeCompare(b.title);
          }
          return b.year - a.year || a.title.localeCompare(b.title);
        });
        visible = PAGE_SIZE;
        renderPapers();
      }

      function renderDebates(debates) {
        var fragment = document.createDocumentFragment();
        debates.forEach(function (debate) {
          var card = element("article", "debate-card");
          card.id = debate.id;
          card.appendChild(element("h2", "", debate.question));
          card.appendChild(element("p", "debate-context", debate.context));
          var sides = element("div", "sides");
          debate.papers.forEach(function (paper) {
            var side = element("section", "side");
            side.appendChild(element("p", "side-meta", paper.venue + " · " + paper.year));
            side.appendChild(paperLink(paper, "h3"));
            side.appendChild(element("p", "", paper.side));
            sides.appendChild(side);
          });
          card.appendChild(sides);
          fragment.appendChild(card);
        });
        byId("debate-list").replaceChildren(fragment);
      }

      byId("search").addEventListener("input", function (event) {
        state.query = event.target.value.trim().toLowerCase();
        applyFilters();
      });
      byId("essential-only").addEventListener("change", function (event) {
        state.essential = event.target.checked;
        applyFilters();
      });
      byId("sort").addEventListener("change", function (event) {
        state.sort = event.target.value;
        applyFilters();
      });
      byId("more-button").addEventListener("click", function () {
        visible += PAGE_SIZE;
        renderPapers();
      });
      byId("clear-button").addEventListener("click", function () {
        state.topic = "all";
        state.venue = "all";
        state.year = "all";
        state.query = "";
        state.essential = false;
        byId("search").value = "";
        byId("essential-only").checked = false;
        byId("filter-groups").querySelectorAll("fieldset").forEach(function (fieldset) {
          fieldset.querySelectorAll(".chip").forEach(function (chip) {
            chip.setAttribute("aria-pressed", String(chip.dataset.value === "all"));
          });
        });
        applyFilters();
        byId("search").focus();
      });

      fetch("papers.json")
        .then(function (response) {
          if (!response.ok) { throw new Error("HTTP " + response.status); }
          return response.json();
        })
        .then(function (data) {
          if (!Array.isArray(data.papers) || !Array.isArray(data.debates)) { throw new Error("Invalid paper data"); }
          papers = data.papers;
          papers.forEach(function (paper) {
            paper.searchText = [paper.title, paper.stance, paper.authors, paper.topic, paper.venue, paper.year].join(" ").toLowerCase();
          });
          buildFilters();
          renderDebates(data.debates);
          applyFilters();
        })
        .catch(function (error) {
          byId("result-count").textContent = "Paper data could not be loaded.";
          byId("empty-state").hidden = false;
          byId("empty-state").replaceChildren(
            element("h2", "", "Unable to load papers"),
            element("p", "load-error", "Serve the docs directory over HTTP and keep papers.json beside index.html.")
          );
          console.error(error);
        })
        .finally(function () { byId("paper-list").setAttribute("aria-busy", "false"); });
    }());
  </script>
</body>
</html>
"""


def build_payload(rows: list[dict], essentials: dict, debates: dict, generated_at: str) -> dict:
    public = [row for row in rows if row.get("excluded", "").lower() != "true"]
    by_id = {row["id"]: row for row in public}
    essential_notes = {item["id"]: item["why"] for item in essentials["papers"]}
    if len(essential_notes) != len(essentials["papers"]):
        raise ValueError("Essential read ids must be unique")

    debate_ids = [debate["id"] for debate in debates["debates"]]
    if len(debate_ids) != len(set(debate_ids)):
        raise ValueError("Debate ids must be unique")
    curated_ids = set(essential_notes)
    curated_ids.update(paper["id"] for debate in debates["debates"] for paper in debate["papers"])
    missing = sorted(curated_ids - set(by_id))
    if missing:
        raise ValueError(f"Curated site ids missing from public CSV: {', '.join(missing)}")

    papers = []
    for row in public:
        citations = int(row["citations"]) if row.get("citations", "").strip() else None
        paper = {
            "id": row["id"],
            "title": row["title"],
            "authors": row["authors"],
            "year": int(row["year"]),
            "venue": row["venue"],
            "topic": row["topic"],
            "url": row["url"],
            "stance": row["stance_summary"],
            "abstract": row["abstract"],
            "citations": citations,
            "essential": row["id"] in essential_notes,
        }
        if paper["essential"]:
            paper["why"] = essential_notes[row["id"]]
        papers.append(paper)

    mapped_debates = []
    for debate in debates["debates"]:
        mapped = {key: debate[key] for key in ("id", "question", "context")}
        mapped["papers"] = []
        for item in debate["papers"]:
            row = by_id[item["id"]]
            mapped["papers"].append({
                "id": row["id"], "title": row["title"], "year": int(row["year"]),
                "venue": row["venue"], "url": row["url"], "side": item["side"],
            })
        mapped_debates.append(mapped)

    return {
        "generated_at": generated_at,
        "papers": papers,
        "debates": mapped_debates,
    }


def build_html(payload: dict) -> str:
    citations_available = any(paper["citations"] is not None for paper in payload["papers"])
    citation_note = ""
    if citations_available and payload.get("citation_fetched_at"):
        citation_note = f" Citations: OpenAlex, {payload['citation_fetched_at']}."
    replacements = {
        "__PAPER_COUNT__": str(len(payload["papers"])),
        "__ESSENTIAL_COUNT__": str(sum(paper["essential"] for paper in payload["papers"])),
        "__DEBATE_COUNT__": str(len(payload["debates"])),
        "__GENERATED_AT__": payload["generated_at"],
        "__CITATION_OPTION__": ('<option value="citations">Citations: most first</option>'
                                 if citations_available else ""),
        "__CITATION_NOTE__": citation_note,
    }
    page = HTML
    for marker, value in replacements.items():
        page = page.replace(marker, value)
    return page


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", default=os.path.join(C.DATA, "papers.csv"))
    parser.add_argument("--stats", default=os.path.join(C.DATA, "stats.json"))
    parser.add_argument("--out", default=os.path.join(C.REPO, "docs"))
    args = parser.parse_args()

    with open(args.stats, encoding="utf-8") as handle:
        stats = json.load(handle)
    essentials = load_yaml(os.path.join(C.DATA, "curated", "essentials.yaml"))
    debates = load_yaml(os.path.join(C.DATA, "curated", "debates.yaml"))
    payload = build_payload(C.read_csv(args.csv), essentials, debates, stats["generated_at"])
    citation_path = os.path.join(C.DATA, "citations.json")
    if os.path.exists(citation_path):
        with open(citation_path, encoding="utf-8") as handle:
            citation_snapshot = json.load(handle)
        payload["citation_source"] = citation_snapshot["source"]
        payload["citation_fetched_at"] = citation_snapshot["fetched_at"]

    os.makedirs(args.out, exist_ok=True)
    json_path = os.path.join(args.out, "papers.json")
    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")
    html_path = os.path.join(args.out, "index.html")
    with open(html_path, "w", encoding="utf-8") as handle:
        handle.write(build_html(payload))

    essential_count = sum(paper["essential"] for paper in payload["papers"])
    citation_count = sum(paper["citations"] is not None for paper in payload["papers"])
    print(f"  wrote {len(payload['papers'])} papers, {essential_count} essentials, "
          f"{len(payload['debates'])} debates -> {os.path.relpath(args.out, C.REPO)}/")
    print(f"  citation sort: {'enabled' if citation_count else 'disabled (no citation data)'}; "
          f"papers.json: {os.path.getsize(json_path):,} bytes")


if __name__ == "__main__":
    main()
