"""Write the ranked CSV, the shortlist CSV and a markdown shortlist a person can read."""
from __future__ import annotations

import csv
import json
from pathlib import Path

OUT_COLS = ["score", "title", "company", "seniority", "remote", "remote_reason", "usd_month",
            "zar_month", "location", "site", "seen_on", "date_posted", "job_url", "why"]
SHORTLIST_COLS = OUT_COLS[:-1] + ["other_roles", "why"]


def _write_csv(path, rows, cols):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({c: ("" if r.get(c) is None else r.get(c)) for c in cols})


def _money(v, sym):
    return f"{sym}{int(v):,}" if v is not None else "not listed"


def write_all(out_dir, ranked, shortlist, summary, rate_note, top=25):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "ranked.csv", ranked, OUT_COLS)
    _write_csv(out / "shortlist.csv", shortlist, SHORTLIST_COLS)
    (out / "summary.json").write_text(json.dumps(dict(summary, rates=rate_note), indent=2),
                                      encoding="utf-8")

    lines = [
        "# Shortlist", "",
        f"{summary['unique_postings']} unique postings. "
        f"{summary['remote_locked']} ({summary['pct_locked']}%) were remote but locked to another "
        f"country. {summary['shortlist']} companies made the shortlist. Pay converted at {rate_note}.",
        "",
        "| # | Score | Role | Company | Pay / month | Remote | Why |",
        "|---|---|---|---|---|---|---|",
    ]
    for i, p in enumerate(shortlist[:top], 1):
        pay = "not listed" if p.get("usd_month") is None else \
            f"{_money(p['usd_month'], '$')} / {_money(p['zar_month'], 'R')}"
        role = f"[{p['title']}]({p['job_url']})" if p.get("job_url") else p["title"]
        more = f" (+{p['other_roles']})" if p.get("other_roles") else ""
        lines.append(f"| {i} | {p['score']} | {role} | {p['company']}{more} | {pay} | "
                     f"{p['remote']}: {p['remote_reason']} | {p['why']} |")
    (out / "shortlist.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
