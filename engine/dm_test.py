"""Diebold-Mariano style paired test: v2t (tl_flat) vs naive "last month's price".

d_t = |actual - naive| - |actual - model|  (> 0 means the model was closer), in USD/MWh.
HAC variance with Bartlett weights, lag h-1 (overlapping h-step forecasts).
"""
import sys
from math import erf, sqrt

import v2t


def dm(h, start="2022-11", path="tl_flat"):
    keys, y, fx, tar = v2t.load_all()
    p = dict(v2t.P, gas_path=path)
    d = []
    for t in range(36, len(y) - h):
        if keys[t + h] < start:
            continue
        f = v2t.forecast(keys, y, fx, tar, t, h, p)
        if f is None:
            continue
        a = y[t + h]
        d.append(abs(a - y[t]) - abs(a - f))
    n = len(d)
    m = sum(d) / n
    g = lambda k: sum((d[i] - m) * (d[i - k] - m) for i in range(k, n)) / n
    lag = max(h - 1, 0)
    var = g(0) + 2 * sum((1 - k / (lag + 1)) * g(k) for k in range(1, lag + 1))
    z = m / sqrt(var / n)
    p_one = 1 - 0.5 * (1 + erf(z / sqrt(2)))
    return n, m, z, p_one, sum(1 for x in d if x > 0)


if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else "2022-11"
    print(f"== v2t (tl_flat) vs naive, {start}+ | gain in USD/MWh ==")
    for h in (1, 3, 6, 12):
        n, m, z, p, w = dm(h, start)
        print(f"h={h:>2} mo | n={n} | mean gain {m:5.2f} USD/MWh | z={z:4.2f} | one-sided p={p:.3f} | model closer {w}/{n}")
