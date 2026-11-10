"""Pay: parse what the ad says, annualise it, and convert it to rand and dollars a month."""
from __future__ import annotations

import json
import math
import re
import urllib.request

# Units of currency per 1 USD. Used only when live ECB rates can't be fetched.
# ECB reference rates, 13 October 2026, rounded.
FALLBACK_PER_USD = {"USD": 1.0, "ZAR": 16.5, "EUR": 0.89, "GBP": 0.75, "CAD": 1.38,
                    "AUD": 1.53, "AED": 3.67, "INR": 86.8}

PERIODS_PER_YEAR = {"yearly": 1, "monthly": 12, "weekly": 52, "daily": 260, "hourly": 2080}

# Anything above this a month is an OTE fantasy or a parsing error, not a salary.
SANE_MAX_USD_MONTH = 40_000


def live_rates(timeout: int = 10) -> tuple[dict, str]:
    """Rates per 1 USD from the ECB (via frankfurter.dev), else the fallback table."""
    try:
        req = urllib.request.Request("https://api.frankfurter.dev/v1/latest?base=USD",
                                     headers={"User-Agent": "job-hunt-pipeline"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            data = json.load(r)
        rates = dict(data["rates"], USD=1.0)
        return rates, f"ECB rates {data.get('date')}"
    except Exception as e:  # offline or API down
        return dict(FALLBACK_PER_USD), f"fallback rates ({e.__class__.__name__})"


def _num(x):
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


def annualise(amount, interval: str | None) -> float | None:
    """Turn an hourly, daily, weekly or monthly figure into a yearly one."""
    v = _num(amount)
    if v is None:
        return None
    return v * PERIODS_PER_YEAR.get((interval or "yearly").lower(), 1)


def convert_monthly(amount, currency: str | None, interval: str | None,
                    rates: dict) -> dict:
    """One advertised figure -> {"usd_month": .., "zar_month": ..}, or Nones if unknown.

    `rates` holds units of currency per 1 USD. Unknown currencies and absurd figures
    come back as None rather than a guess.
    """
    yearly = annualise(amount, interval)
    cur = (currency or "USD").upper()
    if yearly is None or cur not in rates or not rates[cur]:
        return {"usd_month": None, "zar_month": None}
    usd_month = yearly / rates[cur] / 12
    if usd_month > SANE_MAX_USD_MONTH or usd_month < 50:
        return {"usd_month": None, "zar_month": None}
    return {"usd_month": round(usd_month), "zar_month": round(usd_month * rates.get("ZAR", 16.5))}


_SAL_NUM = re.compile(r"(\d[\d,\.]*)\s*(k)?", re.I)


def parse_salary_text(text) -> tuple[float | None, float | None, str | None, str | None]:
    """'$35,3k - $52k', '$120,000 - $150,000', '€60k/year', '$45/hr' -> (min, max, currency, interval).

    Returns the figures as written, with the interval they were written in.
    """
    if not text:
        return None, None, None, None
    t = str(text)
    cur = ("EUR" if "€" in t else "GBP" if "£" in t else
           "ZAR" if re.search(r"\bR\s?\d|\bZAR\b", t) else "USD")
    # South African ads write thousands with a space: "R38 000".
    t = re.sub(r"(?<=\d)[ \u00a0](?=\d{3}(?!\d))", "", t)
    nums = []
    for n, k in _SAL_NUM.findall(t):
        if k and re.fullmatch(r"\d+,\d{1,2}", n):  # "35,3k" uses a decimal comma
            n = n.replace(",", ".")
        try:
            nums.append(float(n.replace(",", "").rstrip(".")) * (1000 if k else 1))
        except ValueError:
            continue
    if not nums:
        return None, None, None, None
    low = t.lower()
    interval = ("hourly" if ("hour" in low or "/hr" in low) else
                "monthly" if ("month" in low or "/mo" in low) else "yearly")
    return min(nums), max(nums), cur, interval
