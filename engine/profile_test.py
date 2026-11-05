"""Kill-condition test for the hourly/daily profile (agreed 2026-11-05).

For each of the last 12 completed months T, as of the month before (t = T-1):
  model : v2t one-month-ahead monthly forecast (run t) distributed with the profile built as of t
  naive : the previous month's (t) average price for the same day type and hour
Also a shape-only check: both shapes scaled to the ACTUAL monthly mean, which isolates the shape.
Errors in USD/MWh; hourly TL/MWh errors use each hour's actual USD/TRY (evaluation only).
"""
import sys
from collections import defaultdict

import profile as pf
import v2t
from calendar_tr import day_type


def naive_shape(H, t_key):
    s, n = defaultdict(float), defaultdict(int)
    for d, h, tl, usd in H[t_key]:
        k = (day_type(d), h)
        s[k] += usd
        n[k] += 1
    allh = defaultdict(list)
    for (dt, h), v in s.items():
        allh[h].append(v / n[(dt, h)])
    return {k: s[k] / n[k] for k in s}, {h: sum(v) / len(v) for h, v in allh.items()}


def run(months):
    keys, y, fx, tar = v2t.load_all()
    P = dict(v2t.P, gas_path="tl_flat")
    H = pf.load_hourly()
    acc = defaultdict(list)
    for T in months:
        i = keys.index(T)
        t = keys[i - 1]
        f = v2t.forecast(keys, y, fx, tar, i - 1, 1, P)
        prof = pf.build(H, t)
        yy, mm = map(int, T.split("-"))
        act = {(d, h): (tl, usd) for d, h, tl, usd in H[T]}
        amean = sum(v[1] for v in act.values()) / len(act)
        ns, nh = naive_shape(H, t)
        tmean = sum(r[3] for r in H[t]) / len(H[t])
        model = pf.distribute(prof, yy, mm, f)
        shape_m = pf.distribute(prof, yy, mm, amean)
        daily = defaultdict(lambda: defaultdict(list))
        for d, h, dt, v in model:
            tl, usd = act[(d, h)]
            nv = ns.get((dt, h), nh[h])
            fxh = tl / usd if usd else 0
            acc["h_model"].append(abs(usd - v))
            acc["h_naive"].append(abs(usd - nv))
            if fxh:
                acc["h_model_tl"].append(abs(tl - v * fxh))
                acc["h_naive_tl"].append(abs(tl - nv * fxh))
            daily[d]["act"].append(usd)
            daily[d]["model"].append(v)
            daily[d]["naive"].append(nv)
        for d, h, dt, v in shape_m:
            usd = act[(d, h)][1]
            nv = ns.get((dt, h), nh[h]) * amean / tmean
            acc["s_model"].append(abs(usd - v))
            acc["s_naive"].append(abs(usd - nv))
        for d, g in daily.items():
            a = sum(g["act"]) / 24
            acc["d_model"].append(abs(a - sum(g["model"]) / 24))
            acc["d_naive"].append(abs(a - sum(g["naive"]) / 24))
    return {k: (sum(v) / len(v), len(v)) for k, v in acc.items()}


if __name__ == "__main__":
    months = sys.argv[1:] or ["2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04", "2026-05",
                              "2026-06", "2026-07", "2026-08", "2026-09", "2026-10"]
    r = run(months)
    print(f"== profile test {months[0]}..{months[-1]} | MAE (lower is better) ==")
    print(f"hourly : model {r['h_model'][0]:7.2f} USD/MWh | naive {r['h_naive'][0]:7.2f} USD/MWh | n={r['h_model'][1]} hours")
    print(f"hourly : model {r['h_model_tl'][0]:7.1f} TL/MWh  | naive {r['h_naive_tl'][0]:7.1f} TL/MWh")
    print(f"daily  : model {r['d_model'][0]:7.2f} USD/MWh | naive {r['d_naive'][0]:7.2f} USD/MWh | n={r['d_model'][1]} days")
    print(f"shape only (both scaled to the actual monthly mean): profile {r['s_model'][0]:7.2f} | last month's shape {r['s_naive'][0]:7.2f} USD/MWh")
