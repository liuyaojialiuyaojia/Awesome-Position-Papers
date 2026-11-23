"""Compute data/stats.json and the two charts from data/papers.csv.

Charts are deliberately plain: white background, direct value labels, no
legend noise, topics sorted by size. Chart 2 shows the topic split by year.
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


def chart_topic_year(df: pd.DataFrame, out: str) -> None:
    frame = df.copy()
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce")
    frame = frame.dropna(subset=["year"])
    frame["year"] = frame["year"].astype(int)
    # Years with only a handful of papers would be an almost empty column:
    # fold them into the next year and label the column as a range.
    per_year = frame["year"].value_counts().sort_index()
    first = min(y for y, n in per_year.items() if n >= 10)
    early = frame["year"] < first
    label = {y: str(y) for y in per_year.index}
    if early.any():
        label[first] = f"{int(frame['year'].min())}–{str(first)[-2:]}"
        frame.loc[early, "year"] = first

    order = list(df["topic"].value_counts().index)
    years = sorted(frame["year"].unique())
    pivot = (frame.groupby(["topic", "year"]).size().unstack("year")
             .reindex(index=order, columns=years).fillna(0))
    values = pivot.values.astype(int)

    fig, ax = plt.subplots(figsize=(7.4, 0.44 * len(order) + 1.8), dpi=170)
    _figure_setup(fig, ax)
    _matrix(ax, order, [label[y] for y in years], values, "year")
    ax.set_title("Position papers per topic, by year", loc="left",
                 fontsize=12, color=INK, pad=12)
    fig.tight_layout()
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
    chart_topic_year(df, os.path.join(C.ASSETS, "papers_per_topic_by_year.png"))

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
        "charts": ["assets/papers_per_topic_by_year.png"],
    }
    C.write_json(stats, os.path.join(C.DATA, "stats.json"))
    print(f"stats: {stats['papers']} papers, {stats['topics']} topics, "
          f"years {stats['years']['min']}-{stats['years']['max']}, "
          f"{stats['with_arxiv_id']} with arXiv id")
    print("  wrote data/stats.json + " + ", ".join(stats["charts"]))


if __name__ == "__main__":
    main()
