"""Command line.

  python -m jobhunt run --profile profile.example.yaml --out out/
  python -m jobhunt run --from-csv sample/postings.csv --out out/   # offline re-run
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

from . import pipeline, report
from .pay import FALLBACK_PER_USD, live_rates
from .profile import load_profile


def _read_csv(path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("min_amount", "max_amount"):
            r[k] = float(r[k]) if r.get(k) not in (None, "") else None
        r["board_scope"] = r.get("board_scope") or None
    return rows


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")  # job titles carry emoji
    ap = argparse.ArgumentParser(prog="jobhunt")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="source, enrich, score and write a shortlist")
    r.add_argument("--profile", default="profile.example.yaml")
    r.add_argument("--out", default="out")
    r.add_argument("--from-csv", help="skip scraping; re-run on a saved raw CSV")
    r.add_argument("--no-jobspy", action="store_true", help="skip Indeed and Glassdoor")
    r.add_argument("--boards", nargs="*", help="remote boards to use (default: all)")
    r.add_argument("--offline-rates", action="store_true", help="use the fixed fallback rates")
    r.add_argument("--save-raw", help="also save the raw scraped rows to this CSV")
    a = ap.parse_args(argv)

    profile = load_profile(a.profile)
    rates, rate_note = ((dict(FALLBACK_PER_USD), "fixed fallback rates (13 Oct 2026)")
                        if a.offline_rates else live_rates())
    status = {}
    if a.from_csv:
        raw = _read_csv(a.from_csv)
    else:
        from .sources import jobspy_boards, remote_boards
        s = profile["search"]
        raw = []
        print("Remote boards:")
        got, status["boards"] = remote_boards.fetch(s["terms"], a.boards)
        raw += got
        if not a.no_jobspy:
            print("JobSpy:")
            got, status["jobspy"] = jobspy_boards.fetch(
                s["terms"], s.get("jobspy_sites", ["indeed", "glassdoor"]),
                s.get("jobspy_countries", ["usa", "uk", "south africa"]),
                s.get("hours_old", 168), s.get("results_per_term", 30))
            raw += got
        if a.save_raw:
            from .normalise import COLUMNS
            with open(a.save_raw, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=COLUMNS, extrasaction="ignore")
                w.writeheader()
                w.writerows(raw)

    if not raw:
        print("No postings. Boards may be blocking or rate-limiting; try fewer terms or later.")
        return 1
    ranked, shortlist, summary = pipeline.run(raw, profile, rates)
    summary["source_status"] = status
    out = report.write_all(a.out, ranked, shortlist, summary, rate_note)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("by_site", "source_status")},
                     indent=2))
    print(f"Wrote {out / 'shortlist.md'}")
    return 0
