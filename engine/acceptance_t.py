"""Acceptance test: tariff engine v2t vs v2 (price-only) vs naive, by horizon. Units: USD/MWh.

Kill condition (agreed 2026-11-05): if v2t does not beat "last month's price"
at both 1 and 3 months over 2022-11+, the page is repositioned as a scenario tool.
"""
import sys

import v2
import v2t


def naive(y, t, h):
    return y[t]


def run(start, horizons=(1, 3, 6, 12), variants=("usd_flat", "tl_flat")):
    keys, y, fx, tar = v2t.load_all()
    out = {}
    for h in horizons:
        rows = {"naive": [], "v2": []}
        for v in variants:
            rows["v2t_" + v] = []
            rows["blend_" + v] = []
        cov = {v: [] for v in variants}
        for t in range(36, len(y) - h):
            if keys[t + h] < start:
                continue
            a = y[t + h]
            ft = {v: v2t.forecast(keys, y, fx, tar, t, h, dict(v2t.P, gas_path=v)) for v in variants}
            if any(f is None for f in ft.values()):
                continue  # same sample for every method
            f2 = v2.forecast(keys, y, t, h)
            rows["naive"].append(abs(a - naive(y, t, h)))
            rows["v2"].append(abs(a - f2))
            for v, f in ft.items():
                rows["v2t_" + v].append(abs(a - f))
                rows["blend_" + v].append(abs(a - (f + f2) / 2))
                b = v2t.band(keys, y, fx, tar, t, h, dict(v2t.P, gas_path=v))
                if b:
                    cov[v].append(f * b[0] <= a <= f * b[1])
        out[h] = {k: (sum(e) / len(e), len(e)) if e else (None, 0) for k, e in rows.items()}
        out[h]["cov"] = {v: ((100 * sum(c) / len(c)) if c else None, len(c)) for v, c in cov.items()}
    return out


def fmt(x):
    return "   n/a" if x is None else f"{x:6.2f}"


if __name__ == "__main__":
    for start in sys.argv[1:] or ["2022-11"]:
        r = run(start)
        print(f"\n== test {start}+ | MAE in USD/MWh (lower is better) | band = 25th-75th pct, target ~50% ==")
        for h, d in r.items():
            n = d["naive"][1]
            line = " | ".join(f"{k} {fmt(v[0])}" for k, v in d.items() if k != "cov")
            cv = " ".join(f"{k}:%{fmt(v[0]).strip()}(n={v[1]})" for k, v in d["cov"].items())
            print(f"h={h:>2} mo | n={n:>2} | {line} | band coverage {cv}")
