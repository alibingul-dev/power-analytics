"""Hourly shape profile: distributes a monthly expected price over days and hours.

NOT an hourly forecast. For as-of month t it uses only hourly prices of the last WINDOW months up to t:
  ratio = hourly USD price / that month's mean USD price
  mult[month-of-year][day type][hour] = mean ratio  (falls back to all months for a day type with
                                                      fewer than MIN_OBS observations)
For a target month the multipliers of its actual calendar are normalised so their hour-weighted mean is 1,
so the hourly (and daily) average always equals the monthly expected value.
Units: USD/MWh unless a name says TL/MWh.
"""
import calendar
import gzip
import csv
from collections import defaultdict
from datetime import date
from pathlib import Path

from calendar_tr import day_type

HOURLY = Path(__file__).parent / "history" / "hourly_ptf.csv.gz"
WINDOW = 36
MIN_DAYS = 6  # days of a (month-of-year, day type) cell needed before falling back to all months
ZERO_TL = 1.5


def load_hourly():
    out = defaultdict(list)  # "YYYY-MM" -> [(date, hour, tl, usd)]
    with gzip.open(HOURLY, "rt") as f:
        for r in csv.DictReader(f):
            d = date.fromisoformat(r["date"])
            out[r["date"][:7]].append((d, int(r["hour"]), float(r["ptf_tl_mwh"]), float(r["ptf_usd_mwh"])))
    return out


def month_keys_back(asof, n):
    y, m = map(int, asof.split("-"))
    ks = []
    for _ in range(n):
        ks.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    return ks


def build(H, asof):
    """Profile from the WINDOW months ending at asof (inclusive). Returns dict with mult and stats."""
    s = defaultdict(float)
    n = defaultdict(int)
    s_all = defaultdict(float)
    n_all = defaultdict(int)
    zero = defaultdict(list)
    topm = defaultdict(list)
    for k in month_keys_back(asof, WINDOW):
        rows = H.get(k)
        if not rows:
            continue
        mean = sum(r[3] for r in rows) / len(rows)
        mx = max(r[2] for r in rows)
        moy = int(k[5:])
        zero[moy].append(sum(1 for r in rows if r[2] <= ZERO_TL))
        topm[moy].append(sum(1 for r in rows if r[2] >= mx - 0.01))
        if mean <= 0:
            continue
        for d, h, tl, usd in rows:
            dt = day_type(d)
            s[(moy, dt, h)] += usd / mean
            n[(moy, dt, h)] += 1
            s_all[(dt, h)] += usd / mean
            n_all[(dt, h)] += 1
    mult = {}
    for moy in range(1, 13):
        for dt in range(3):
            for h in range(24):
                k = (moy, dt, h)
                if n[k] >= MIN_DAYS:
                    mult[k] = s[k] / n[k]
                else:
                    mult[k] = s_all[(dt, h)] / n_all[(dt, h)] if n_all[(dt, h)] else 1.0
    return dict(asof=asof, mult=mult,
                zero_hours={m: round(sum(v) / len(v), 1) for m, v in zero.items()},
                top_hours={m: round(sum(v) / len(v), 1) for m, v in topm.items()},
                months_used=[k for k in month_keys_back(asof, WINDOW) if k in H])


def distribute(prof, y, m, monthly_usd):
    """Hourly list [(date, hour, day_type, usd)] for month y-m whose hour-weighted mean equals monthly_usd."""
    nd = calendar.monthrange(y, m)[1]
    cells = []
    for dd in range(1, nd + 1):
        d = date(y, m, dd)
        dt = day_type(d)
        for h in range(24):
            cells.append((d, h, dt, prof["mult"][(m, dt, h)]))
    norm = sum(c[3] for c in cells) / len(cells)
    return [(d, h, dt, monthly_usd * w / norm) for d, h, dt, w in cells]


def compact(prof):
    """Small JSON form for the page: mult[moy-1][day type][hour], rounded."""
    return dict(window_months=WINDOW, months_used=[prof["months_used"][-1], prof["months_used"][0]],
                mult=[[[round(prof["mult"][(m, dt, h)], 4) for h in range(24)] for dt in range(3)] for m in range(1, 13)],
                zero_hours=[prof["zero_hours"].get(m) for m in range(1, 13)],
                top_hours=[prof["top_hours"].get(m) for m in range(1, 13)])
