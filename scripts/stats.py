"""Compute data/stats.json and the two README charts from data/papers.csv.

Charts are deliberately plain: white background, direct value labels, no
legend noise, topics sorted by size. Chart 2 is a two-panel matrix so the
topic split is readable both by year and by venue.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, __file__.rsplit("/", 1)[0])
import common as C  # noqa: E402

BG = "#ffffff"
INK = "#1f2328"
SOFT = "#57606a"
BLUE = "#3b7dd8"
GRID = "#eaeef2"


def _figure_setup(fig, ax) -> None:
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.tick_params(colors=SOFT, length=0)


def chart_topic(df: pd.DataFrame, out: str) -> None:
    counts = df["topic"].value_counts(ascending=True)
    fig, ax = plt.subplots(figsize=(7.4, 0.44 * len(counts) + 1.5), dpi=170)
    _figure_setup(fig, ax)
    bars = ax.barh(counts.index, counts.values, color=BLUE, height=0.62)
    ax.set_xlim(0, counts.max() * 1.14)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for b, v in zip(bars, counts.values):
        ax.text(v + counts.max() * 0.012, b.get_y() + b.get_height() / 2, str(v),
                va="center", ha="left", fontsize=8.5, color=SOFT)
    ax.set_xlabel("papers", fontsize=9, color=SOFT)
    ax.set_title("Position papers per topic", loc="left", fontsize=12, color=INK, pad=12)
    fig.tight_layout()
    fig.savefig(out, facecolor=BG)
    plt.close(fig)


def _matrix(ax, labels: list[str], cols: list[str], values: np.ndarray,
            colname: str) -> float:
    """Draw one annotated count matrix; returns the axis width used for labels."""
    vmax = max(int(values.max()), 1)
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list(
        "softblue", ["#f5f9fe", "#cfe1f7", "#7fb0e8", BLUE])
    im = ax.imshow(values, cmap=cmap, aspect="auto", vmin=0, vmax=vmax)
    ax.set_xticks(range(len(cols)), cols, fontsize=8.5)
    ax.set_yticks(range(len(labels)), labels, fontsize=8.5)
    ax.tick_params(length=0)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    for i in range(values.shape[0]):
        for j in range(values.shape[1]):
            v = int(values[i, j])
            if v == 0:
                continue
            dark = values[i, j] > 0.72 * vmax
            ax.text(j, i, str(v), ha="center", va="center", fontsize=7.6,
                    color="#ffffff" if dark else INK)
    ax.set_xlabel(colname, fontsize=9, color=SOFT)
    return vmax


def chart_topic_split(df: pd.DataFrame, out: str) -> None:
    frame = df.copy()
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce")
    frame = frame.dropna(subset=["year"])
    frame["year"] = frame["year"].astype(int)

    order = list(df["topic"].value_counts().index)          # biggest first
    years = sorted(frame["year"].unique())
    venues = [v for v in ["ICML", "NeurIPS", "arXiv-only"] if v in set(frame["venue"])]
    venues += sorted(set(frame["venue"]) - set(venues))

    def grid(col: str, cols: list) -> np.ndarray:
        pivot = (frame.groupby(["topic", col]).size().unstack(col)
                 .reindex(index=order, columns=cols).fillna(0))
        return pivot.values.astype(int)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 0.36 * len(order) + 2.4), dpi=170,
                                   gridspec_kw={"width_ratios": [len(years), max(len(venues), 3) + 1]})
    fig.patch.set_facecolor(BG)
    _matrix(ax1, order, [str(y) for y in years], grid("year", years), "year")
    _matrix(ax2, order, venues, grid("venue", venues), "venue")
    for ax in (ax1, ax2):
        _figure_setup(fig, ax)
        ax.set_yticklabels([])
    ax2.set_yticks(range(len(order)), order, fontsize=8.5)
    ax2.set_yticklabels(order, fontsize=8.5)
    fig.suptitle("Position papers per topic, by year and by venue",
                 x=0.012, y=0.995, ha="left", fontsize=12, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.955))
    fig.savefig(out, facecolor=BG)
    plt.close(fig)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=os.path.join(C.DATA, "papers.csv"))
    args = ap.parse_args()

    df = pd.read_csv(args.csv, keep_default_na=False)
    if "excluded" in df:
        df = df[df["excluded"].astype(str).str.lower() != "true"].copy()
    df["year"] = pd.to_numeric(df["year"], errors="coerce")

    os.makedirs(C.ASSETS, exist_ok=True)
    chart_topic(df, os.path.join(C.ASSETS, "papers_per_topic.png"))
    chart_topic_split(df, os.path.join(C.ASSETS, "papers_per_topic_by_year_venue.png"))

    def counts(col: str) -> dict:
        vc = df[col].fillna("").astype(str).replace("", "unspecified").value_counts()
        return {str(k): int(v) for k, v in vc.items()}

    topic_year: dict[str, dict[str, int]] = {}
    for (topic, year), n in df.dropna(subset=["year"]).groupby(["topic", "year"]).size().items():
        topic_year.setdefault(str(topic), {})[str(int(year))] = int(n)

    # Which venue/year combinations the data actually contains: the README
    # builds its coverage sentence from this, so it cannot claim a track that
    # produced no rows (or miss one that did).
    venue_year: dict[str, dict[str, int]] = {}
    for (venue, year), n in df.dropna(subset=["year"]).groupby(["venue", "year"]).size().items():
        venue_year.setdefault(str(venue), {})[str(int(year))] = int(n)

    track_year: dict[str, dict[str, int]] = {}
    for (track, year), n in df.dropna(subset=["year"]).groupby(["track", "year"]).size().items():
        if str(track):
            track_year.setdefault(str(track), {})[str(int(year))] = int(n)

    stats = {
        "generated_at": dt.date.today().isoformat(),
        "papers": int(len(df)),
        "topics": int(df["topic"].nunique()),
        "years": {"min": int(df["year"].min()), "max": int(df["year"].max())},
        "per_topic": counts("topic"),
        "per_venue": counts("venue"),
        "per_year": {str(int(k)): int(v) for k, v in df["year"].value_counts().sort_index().items()},
        "per_source": counts("source"),
        "per_topic_year": topic_year,
        "per_venue_year": venue_year,
        "per_track_year": track_year,
        "with_arxiv_id": int((df["arxiv_id"].astype(str).str.len() > 0).sum()),
        "charts": ["assets/papers_per_topic.png", "assets/papers_per_topic_by_year_venue.png"],
    }
    C.write_json(stats, os.path.join(C.DATA, "stats.json"))
    print(f"stats: {stats['papers']} papers, {stats['topics']} topics, "
          f"years {stats['years']['min']}-{stats['years']['max']}, "
          f"{stats['with_arxiv_id']} with arXiv id")
    print("  wrote data/stats.json + " + ", ".join(stats["charts"]))


if __name__ == "__main__":
    main()
