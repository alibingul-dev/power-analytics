"""Pre-declared alternative (2026-11-05): last month's day-type x hour shape, normalised over the
target month's calendar, scaled to the v2t one-month-ahead level. Same 12 months as profile_test.py."""
import calendar
from collections import defaultdict
from datetime import date
import profile as pf
import v2t
from calendar_tr import day_type

keys, y, fx, tar = v2t.load_all(); P = dict(v2t.P, gas_path="tl_flat"); H = pf.load_hourly()
months = ["2025-11","2025-12","2026-01","2026-02","2026-03","2026-04","2026-05","2026-06","2026-07","2026-08","2026-09","2026-10"]
acc = defaultdict(list)
for T in months:
    i = keys.index(T); t = keys[i-1]
    f = v2t.forecast(keys, y, fx, tar, i-1, 1, P)
    s, n = defaultdict(float), defaultdict(int)
    for d, h, tl, usd in H[t]:
        s[(day_type(d), h)] += usd; n[(day_type(d), h)] += 1
    tmean = sum(r[3] for r in H[t]) / len(H[t])
    byh = defaultdict(list)
    for (dt, h), v in s.items(): byh[h].append(v / n[(dt, h)])
    shp = lambda dt, h: (s[(dt, h)] / n[(dt, h)] if n[(dt, h)] else sum(byh[h]) / len(byh[h])) / tmean
    yy, mm = map(int, T.split("-"))
    cells = [(date(yy, mm, dd), h) for dd in range(1, calendar.monthrange(yy, mm)[1] + 1) for h in range(24)]
    w = {c: shp(day_type(c[0]), c[1]) for c in cells}; norm = sum(w.values()) / len(w)
    act = {(d, h): usd for d, h, tl, usd in H[T]}
    day = defaultdict(lambda: [0.0, 0.0, 0.0])
    for c in cells:
        alt = f * w[c] / norm; nv = shp(day_type(c[0]), c[1]) * tmean
        acc["alt"].append(abs(act[c] - alt)); acc["naive"].append(abs(act[c] - nv))
        dd = day[c[0]]; dd[0] += act[c] / 24; dd[1] += alt / 24; dd[2] += nv / 24
    for a, m, nv in day.values():
        acc["d_alt"].append(abs(a - m)); acc["d_naive"].append(abs(a - nv))
mae = lambda k: sum(acc[k]) / len(acc[k])
print(f"hourly: alternative {mae('alt'):.2f} USD/MWh | naive {mae('naive'):.2f} USD/MWh | profile (profile_test.py) 16.03 USD/MWh")
print(f"daily : alternative {mae('d_alt'):.2f} USD/MWh | naive {mae('d_naive'):.2f} USD/MWh | profile 11.21 USD/MWh")
