"""Pre-declared April tariff-step variants vs today's engine (TL-flat). Leak-free. USD/MWh."""
import calendar, math
from math import erf, sqrt
import v2t
keys, y, fx, tar = v2t.load_all()
V = {"bugünkü (TL'de sabit)": "tl_flat", "(a) son 12 ay değişimi kadar Nisan zammı": "april_trail", "(b) kaybedilen dolar değerini geri getiren Nisan zammı": "april_restore"}
P = lambda g: dict(v2t.P, gas_path=g)
def errs(g, h, a="2022-11", b="2026-10"):
    out = {}
    for t in range(len(y) - h):
        if not (a <= keys[t + h] <= b): continue
        fs = {n: v2t.forecast(keys, y, fx, tar, t, h, P(gg)) for n, gg in V.items()}
        if any(f is None for f in fs.values()): continue
        out[t] = (y[t + h] - fs[[n for n in V if V[n] == g][0]], y[t + h] - y[t])
    return out
def dm(d, h):
    n = len(d); m = sum(d) / n; gg = lambda k: sum((d[i] - m) * (d[i - k] - m) for i in range(k, n)) / n
    L = max(h - 1, 0); var = gg(0) + 2 * sum((1 - k / (L + 1)) * gg(k) for k in range(1, L + 1))
    z = m / sqrt(var / n) if var > 0 else 0; return m, 1 - 0.5 * (1 + erf(z / sqrt(2)))
H = (1, 3, 6, 12, 18, 24)
print("== MAE USD/MWh, 2022-11..2026-10, common sample ==")
print(f"{'varyant':58s}" + "".join(f"{'h='+str(h):>8s}" for h in H))
base = {h: errs("tl_flat", h) for h in H}
for n, g in V.items():
    e = {h: errs(g, h) for h in H}
    print(f"{n:58s}" + "".join(f"{sum(abs(v[0]) for v in e[h].values())/len(e[h]):8.2f}" for h in H))
print(f"{'geçen ayın fiyatı':58s}" + "".join(f"{sum(abs(v[1]) for v in base[h].values())/len(base[h]):8.2f}" for h in H))
print("n:", {h: len(base[h]) for h in H})
print("\n== Bias h=6/12 (actual - forecast, USD/MWh) and DM vs today (positive = variant better) ==")
for n, g in V.items():
    if g == "tl_flat": continue
    e = {h: errs(g, h) for h in H}
    bias = " ".join(f"{sum(v[0] for v in e[h].values())/len(e[h]):6.2f}" for h in (6, 12))
    dms = " | ".join("h=%d: %+.2f p=%.3f" % ((h,) + dm([abs(base[h][t][0]) - abs(e[h][t][0]) for t in sorted(e[h])], h)) for h in (6, 12, 24))
    print(f"   {n:56s} bias {bias} | {dms}")
print("   bugünkü bias h=6/12:", " ".join(f"{sum(v[0] for v in base[h].values())/len(base[h]):6.2f}" for h in (6, 12)))
print("\n== Sub-period 2024-11..2026-10, MAE h=6/12 ==")
for n, g in V.items():
    print(f"   {n:56s} " + " ".join(f"{sum(abs(v[0]) for v in errs(g,h,'2024-11','2026-10').values())/len(errs(g,h,'2024-11','2026-10')):7.2f}" for h in (6, 12)))
print("\n== Cal-27 from the 2026-10 run (USD/MWh) ==")
t = keys.index("2026-10")
for n, g in V.items():
    num = den = 0
    for h in range(1, 25):
        yy, mm = 2026 + (10 + h - 1) // 12, (10 + h - 1) % 12 + 1
        if yy != 2027: continue
        hrs = 24 * calendar.monthrange(yy, mm)[1]; num += v2t.forecast(keys, y, fx, tar, t, h, P(g)) * hrs; den += hrs
    print(f"   {n:56s} {num/den:6.2f}")
