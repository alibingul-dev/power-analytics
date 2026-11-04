"""Price Outlook Lab engine v2 — baselines and walk-forward harness.

Every forecast for month t+h is made with data available at the end of month t
(as_of = t): monthly PTF is known once the month closes. Units: USD/MWh.
"""
import json, math, statistics as st, sys
from pathlib import Path

HIST = Path(__file__).parent / "history" / "monthly_ptf.json"


def load():
    m = json.load(open(HIST))["months"]
    m = [x for x in m if x.get("complete", True)]
    return [x["month"] for x in m], [x["ptf_usd_mwh"] for x in m]


def naive(y, t, h):
    """Last closed month's price."""
    return y[t]


def seasonal_naive(y, t, h):
    """Same calendar month one year earlier (t+h-12), only if already known."""
    k = t + h - 12
    return y[k] if 0 <= k <= t else None


def mae(errs):
    return sum(abs(e) for e in errs) / len(errs) if errs else None


def evaluate(fn, keys, y, start, h=1):
    errs = []
    for t in range(len(y) - h):
        if keys[t + h] < start:
            continue
        f = fn(y, t, h)
        if f is None:
            continue
        errs.append(y[t + h] - f)
    return mae(errs), len(errs)


if __name__ == "__main__":
    keys, y = load()
    for start in ("2018-01", "2022-11", "2025-11"):
        for name, fn in (("naive (son ay)", naive), ("seasonal naive (gecen yil ayni ay)", seasonal_naive)):
            v, n = evaluate(fn, keys, y, start)
            print(f"{start}+ | {name:36s} | 1 ay MAE {v:6.2f} $/MWh | n={n}")
