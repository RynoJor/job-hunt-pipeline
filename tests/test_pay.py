import pytest

from jobhunt.pay import FALLBACK_PER_USD, annualise, convert_monthly, parse_salary_text

RATES = {"USD": 1.0, "ZAR": 18.0, "EUR": 0.9, "GBP": 0.75}


def test_annualise_periods():
    assert annualise(50, "hourly") == 50 * 2080
    assert annualise(4000, "monthly") == 48000
    assert annualise(1000, "weekly") == 52000
    assert annualise(90000, "yearly") == 90000
    assert annualise(90000, None) == 90000
    assert annualise(None, "yearly") is None
    assert annualise(float("nan"), "yearly") is None


def test_usd_yearly_to_monthly_usd_and_zar():
    assert convert_monthly(120000, "USD", "yearly", RATES) == {"usd_month": 10000, "zar_month": 180000}


def test_other_currency_goes_through_usd():
    # 90,000 EUR a year = 100,000 USD a year = 8,333 USD a month.
    out = convert_monthly(90000, "EUR", "yearly", RATES)
    assert out["usd_month"] == 8333
    assert out["zar_month"] == round(8333.33 * 18)


def test_hourly_rate():
    assert convert_monthly(50, "USD", "hourly", RATES)["usd_month"] == round(50 * 2080 / 12)


def test_rand_salary():
    assert convert_monthly(42000, "ZAR", "monthly", RATES) == {"usd_month": round(42000 / 18),
                                                               "zar_month": 42000}


@pytest.mark.parametrize("amount, cur, interval", [
    (None, "USD", "yearly"),            # nothing advertised
    (100000, "XYZ", "yearly"),          # unknown currency: no guess
    (5_000_000, "USD", "yearly"),       # OTE fantasy or a parsing error
    (12, "USD", "yearly"),              # stray number, not a salary
])
def test_unknowns_and_nonsense_return_none(amount, cur, interval):
    assert convert_monthly(amount, cur, interval, RATES) == {"usd_month": None, "zar_month": None}


@pytest.mark.parametrize("text, expected", [
    ("$120,000 - $150,000", (120000, 150000, "USD", "yearly")),
    ("$35,3k - $52k", (35300, 52000, "USD", "yearly")),
    ("€60k/year", (60000, 60000, "EUR", "yearly")),
    ("£4,000 per month", (4000, 4000, "GBP", "monthly")),
    ("$45/hr", (45, 45, "USD", "hourly")),
    ("R38 000 - R42 000 per month", (38000, 42000, "ZAR", "monthly")),
    ("", (None, None, None, None)),
    ("Competitive", (None, None, None, None)),
])
def test_parse_salary_text(text, expected):
    lo, hi, cur, iv = parse_salary_text(text)
    assert (lo, hi, cur, iv) == expected


def test_fallback_table_has_rand():
    assert FALLBACK_PER_USD["ZAR"] > 10
