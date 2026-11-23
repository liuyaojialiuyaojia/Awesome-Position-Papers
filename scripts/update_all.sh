#!/usr/bin/env bash
# Rebuild everything from public sources, in order. Raw responses are cached
# under .cache/, so a second run makes almost no network requests.
# Usage: bash scripts/update_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."

[ -x .venv/bin/python ] || { python3 -m venv .venv; .venv/bin/pip install -q -r requirements.txt; }
py() { echo "+ $*"; .venv/bin/python "$@"; }

py scripts/collect_icml.py --year 2024
py scripts/collect_icml.py --year 2025
py scripts/collect_icml.py --year 2026
py scripts/collect_neurips.py --year 2025
py scripts/collect_neurips.py --year 2026
py scripts/collect_arxiv.py
py scripts/build_dataset.py
py scripts/fetch_citations.py
py scripts/stats.py
py scripts/build_readme.py
py scripts/build_site.py
py scripts/needs_curation.py
