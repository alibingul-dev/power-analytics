"""Horizon-by-horizon acceptance test for engine v2 vs naive baselines. Units: USD/MWh."""
import math, sys
from baselines import load
import v2

def naive(keys, y, t, h): return y[t]
def snaive(keys, y, t, h):
    k = t + h - 12
    while k > t: k -= 12
    return y[k] if k >= 0 else None

def run(start, horizons=(1, 3, 6, 12), min_train=36):
    keys, y = load()
    out = {}
    for h in horizons:
        e = {"v2": [], "naive": [], "snaive": []}; cov = []
        for t in range(min_train, len(y) - h):
            if keys[t + h] < start: continue
            a = y[t + h]
            for name, fn in (("v2", lambda *z: v2.forecast(*z)), ("naive", naive), ("snaive", snaive)):
                f = fn(keys, y, t, h)
                if f is not None: e[name].append(abs(a - f))
            b = v2.band(keys, y, t, h)
            if b:
                f = v2.forecast(keys, y, t, h)
                cov.append(f * b[0] <= a <= f * b[1])
        out[h] = {k: (sum(v) / len(v), len(v)) for k, v in e.items()}
        out[h]["cov"] = (100 * sum(cov) / len(cov), len(cov)) if cov else (None, 0)
    return out

if __name__ == "__main__":
    for start in sys.argv[1:] or ["2020-01", "2022-11"]:
        r = run(start)
        print(f"\n== test {start}+ (MAE $/MWh; band = 25th–75th, target ~50%) ==")
        for h, d in r.items():
            print(f"h={h:>2} ay | v2 {d['v2'][0]:6.2f} | naive {d['naive'][0]:6.2f} | geçen yıl {d['snaive'][0]:6.2f} | bant kapsaması %{d['cov'][0]:.0f} | n={d['v2'][1]}")
