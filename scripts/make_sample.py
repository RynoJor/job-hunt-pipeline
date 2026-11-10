"""Cut a full raw run down to a small sample that is safe to commit.

  python scripts/make_sample.py raw.csv sample/postings.csv --n 50

- Picks about n postings spread across boards and across open / locked / unclear verdicts.
- Trims each ad to a short window around the evidence the remote detector used, so the
  verdict still re-computes from the sample and the file stays small.
- Leaves out any company named in --exclude.
- Strips email addresses and phone numbers that some ads carry for their recruiters.
"""
import argparse
import csv
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from jobhunt.normalise import COLUMNS, company_key, normalise  # noqa: E402
from jobhunt.remote import check_remote_eligibility  # noqa: E402

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"\+?\d[\d ()-]{7,}\d")
URL = re.compile(r"https?://\S+")


def trim(desc, reason, width=350):
    m = re.search(r"'([^']+)'", reason)
    i = desc.lower().find(m.group(1).lower()) if m else -1
    if i < 0:
        return desc[:2 * width]
    return desc[max(0, i - width): i + width]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("raw")
    ap.add_argument("out")
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--exclude", help="text file, one company per line, to leave out")
    a = ap.parse_args()

    with open(a.raw, encoding="utf-8") as f:
        rows = [normalise(r) for r in csv.DictReader(f)]
    skip = set()
    if a.exclude:
        skip = {company_key(c) for c in open(a.exclude, encoding="utf-8").read().splitlines() if c.strip()}
    seen, pool = set(), []
    for r in rows:
        key = (r["company_key"], r["title_key"])
        if not r["title"] or not r["company"] or key in seen or r["company_key"] in skip:
            continue
        seen.add(key)
        v = check_remote_eligibility(r["title"], r["location"] or "", r["description"],
                                     r["board_scope"])
        pool.append((r, v))

    rng = random.Random(a.seed)
    rng.shuffle(pool)
    groups = {}
    for r, v in pool:
        groups.setdefault((r["site"], v.label), []).append((r, v))
    picked, keys = [], sorted(groups)
    while len(picked) < a.n and any(groups.values()):
        for k in keys:
            if groups[k] and len(picked) < a.n:
                picked.append(groups[k].pop())

    with open(a.out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r, v in picked:
            desc = trim(r["description"], v.reason)
            desc = PHONE.sub("[phone removed]", EMAIL.sub("[email removed]", URL.sub("", desc)))
            w.writerow({c: ("" if r.get(c) is None else r[c]) for c in COLUMNS} | {"description": desc})
    print(f"wrote {len(picked)} postings to {a.out}")


if __name__ == "__main__":
    main()
