"""Stress test of the PTF/G long-run ratio (2026-11-05). Leak-free walk-forward, tariff engine (TL-flat).
Units: USD/MWh. Fixed-value variants (1.0348, 0.82) are hindsight constants: flagged."""
import math, sys
from math import erf, sqrt
import v2t

keys, y, fx, tar = v2t.load_all()
B = dict(v2t.P, gas_path="tl_flat")
V = {
  "bugünkü: ort. son 24 ay (0,82)": dict(B),
  "ort. son 6 ay": dict(B, level_window=6),
  "ort. son 12 ay": dict(B, level_window=12),
  "ort. son 36 ay": dict(B, level_window=36),
  "ort. genişleyen": dict(B, mu_stat="expanding"),
  "medyan son 24 ay": dict(B, mu_stat="median", mu_window=24),
  "medyan son 36 ay": dict(B, mu_stat="median", mu_window=36),
  "medyan genişleyen": dict(B, mu_stat="median"),
  "sabit 1,0348 (eski, geriye bakış)": dict(B, mu_fixed=1.0348),
  "sabit 0,82 (geriye bakış)": dict(B, mu_fixed=0.82),
}
H = (1, 3, 6, 12, 18, 24)
PER = [("2022-11", "2026-10", "tüm"), ("2022-11", "2024-10", "2022-11..2024-10"), ("2024-11", "2026-10", "2024-11..2026-10"), ("2026-01", "2026-10", "2026 çöküş yılı")]
cache = {}
def fc(name, t, h):
    k = (name, t, h)
    if k not in cache:
        cache[k] = v2t.forecast(keys, y, fx, tar, t, h, V[name])
    return cache[k]

def errs(name, h, a, b):
    out = []
    for t in range(len(y) - h):
        if not (a <= keys[t + h] <= b): continue
        f = fc(name, t, h)
        if f is None or any(fc(n, t, h) is None for n in V): continue  # common sample
        out.append((y[t + h] - f, y[t + h] - y[t], t))
    return out

def dm(d, h):
    n = len(d); m = sum(d) / n
    g = lambda k: sum((d[i] - m) * (d[i - k] - m) for i in range(k, n)) / n
    L = max(h - 1, 0); var = g(0) + 2 * sum((1 - k / (L + 1)) * g(k) for k in range(1, L + 1))
    z = m / sqrt(var / n) if var > 0 else 0.0
    return m, z, 1 - 0.5 * (1 + erf(z / sqrt(2)))

print("== MAE (USD/MWh) by horizon, common sample, test 2022-11..2026-10 | lower is better ==")
print(f"{'varyant':38s}" + "".join(f"{'h='+str(h):>9s}" for h in H) + f"{'ort.sıra':>10s}")
ranks = {n: [] for n in V}; table = {}
for h in H:
    row = {n: sum(abs(e[0]) for e in errs(n, h, "2022-11", "2026-10")) / len(errs(n, h, "2022-11", "2026-10")) for n in V}
    for i, n in enumerate(sorted(row, key=row.get)): ranks[n].append(i + 1)
    table[h] = row
nv = {h: sum(abs(e[1]) for e in errs("bugünkü: ort. son 24 ay (0,82)", h, "2022-11", "2026-10")) / len(errs("bugünkü: ort. son 24 ay (0,82)", h, "2022-11", "2026-10")) for h in H}
for n in V:
    print(f"{n:38s}" + "".join(f"{table[h][n]:9.2f}" for h in H) + f"{sum(ranks[n])/len(H):10.1f}")
print(f"{'geçen ayın fiyatı (naive)':38s}" + "".join(f"{nv[h]:9.2f}" for h in H))
print("n (ay):", {h: len(errs("bugünkü: ort. son 24 ay (0,82)", h, "2022-11", "2026-10")) for h in H})

print("\n== Sub-periods, MAE USD/MWh at h=1 / 6 / 12 ==")
for a, b, lab in PER[1:]:
    print(f"-- {lab}")
    for n in V:
        vals = []
        for h in (1, 6, 12):
            e = errs(n, h, a, b); vals.append(f"{sum(abs(x[0]) for x in e)/len(e):7.2f}(n={len(e)})" if e else "    n/a")
        print(f"   {n:36s} " + " ".join(vals))

print("\n== Bias (mean actual - forecast, USD/MWh) at h=6 / 12; + = model too low ==")
for n in V:
    print(f"   {n:36s} " + " ".join(f"{sum(x[0] for x in errs(n,h,'2022-11','2026-10'))/len(errs(n,h,'2022-11','2026-10')):7.2f}" for h in (6, 12)))

print("\n== Diebold-Mariano vs today's engine (positive = variant better), one-sided p ==")
for n in V:
    if n.startswith("bugünkü"): continue
    out = []
    for h in (1, 6, 12):
        A = {x[2]: abs(x[0]) for x in errs("bugünkü: ort. son 24 ay (0,82)", h, "2022-11", "2026-10")}
        Bv = {x[2]: abs(x[0]) for x in errs(n, h, "2022-11", "2026-10")}
        d = [A[t] - Bv[t] for t in sorted(A) if t in Bv]
        m, z, p = dm(d, h); out.append(f"h={h}: {m:+6.2f} p={p:.3f}")
    print(f"   {n:36s} " + " | ".join(out))

print("\n== Cal-27 (USD/MWh, hour-weighted 2027 average) from the 2026-10 run ==")
import calendar
t = keys.index("2026-10")
for n in V:
    num = den = 0.0
    for h in range(1, 25):
        yy, mm = 2026 + (10 + h - 1) // 12, (10 + h - 1) % 12 + 1
        if yy != 2027: continue
        hrs = 24 * calendar.monthrange(yy, mm)[1]; num += v2t.forecast(keys, y, fx, tar, t, h, V[n]) * hrs; den += hrs
    print(f"   {n:36s} {num/den:7.2f} USD/MWh")
