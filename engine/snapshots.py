"""Build every Price Outlook Lab run file from engine v2t — one command, no hand edits.

    python3 engine/snapshots.py

Writes (all prices USD/MWh, tariff TL/1000 Sm3, FX TRY per USD):
  outlook/snapshots/v2t/<YYYY-MM>.json  one run per as-of month: engine state + curve + band
  outlook/snapshots/index.json          list of runs, versions and the backtest summary
  realized/monthly.json                 completed monthly PTF from engine/history

Leak-free: the run for as-of month t uses price, FX and tariff up to and including t only,
and its band uses only forecast errors whose outcome was known by t.
"""
import calendar
import json
import math
from pathlib import Path

import v2
import v2t
from dm_test import dm

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outlook" / "snapshots" / "v2t"
ENGINE_VERSION = "v2t-1.0"
HORIZON = 24  # longest horizon with a leak-free test (h=24: n=34, MAE 22.64 vs naive 45.55 USD/MWh)
P = dict(v2t.P, gas_path="tl_flat")


def add_months(key, h):
    y, m = map(int, key.split("-"))
    m += h
    y += (m - 1) // 12
    m = (m - 1) % 12 + 1
    return y, m


def state(keys, y, fx, tar, t):
    """Engine state at as-of month t, enough for the page to recompute the curve with other inputs."""
    ly = [math.log(max(v, 0.5)) for v in y[: t + 1]]
    s = v2.seasonal(keys, ly, t, v2.P["season_window"])
    R = [ly[i] - math.log(v2t.gas_cost(tar[i], fx[i])) - s(v2._month(keys[i]))
         for i in range(t + 1) if tar[i] is not None]
    win = R[-P["level_window"]:]
    mu = sum(win) / len(win)
    x, z = [a - mu for a in win[:-1]], [a - mu for a in win[1:]]
    den = sum(a * a for a in x)
    phi = min(P["phi_max"], max(P["phi_min"], sum(a * b for a, b in zip(x, z)) / den if den else 0.8))
    k = max(0, t - 12)
    drift = (math.log(fx[t]) - math.log(fx[k])) / (t - k)
    return dict(seasonal=[round(s(m), 6) for m in range(1, 13)], mu=round(mu, 6), phi=round(phi, 6),
                R_last=round(R[-1], 6), fx_drift_log=round(drift, 6))


def run_file(keys, y, fx, tar, t, tariff_version):
    st = state(keys, y, fx, tar, t)
    months = []
    for h in range(1, HORIZON + 1):
        f = v2t.forecast(keys, y, fx, tar, t, h, P)
        w = v2t.band_halfwidth(keys, y, fx, tar, t, h, P)
        yy, mm = add_months(keys[t], h)
        months.append(dict(j=h, y=yy, m=mm, hours=24 * calendar.monthrange(yy, mm)[1],
                           exp=round(f, 2), half=round(w, 4),
                           lo=round(f * math.exp(-w), 2), hi=round(f * math.exp(w), 2)))
    # scorecard: the last 12 completed months, each called one month ahead by the run before it
    score = []
    for i in range(max(1, t - 11), t + 1):
        f = v2t.forecast(keys, y, fx, tar, i - 1, 1, P)
        if f is not None:
            score.append(dict(k=keys[i], said=round(f, 2), naive=y[i - 1], act=y[i]))
    hw1 = [v2t.band_halfwidth(keys, y, fx, tar, i, 1, P) for i in range(max(0, t - 35), t + 1)]
    hw1 = [v for v in hw1 if v is not None]
    regime = "stormy" if hw1 and months[0]["half"] > sorted(hw1)[len(hw1) // 2] else "calm"
    return dict(
        engine_version=ENGINE_VERSION, data_cutoff=keys[t], tariff_series_version=tariff_version,
        units=dict(price="USD/MWh", tariff="TL/1000 Sm3", fx="TRY per USD"),
        cut=keys[t], last_usd=y[t], last_fx=fx[t], tariff=tar[t],
        gas_cost=round(v2t.gas_cost(tar[t], fx[t]), 3), conv=dict(mwh_per_ksm3=v2t.MWH_PER_KSM3, eff=v2t.EFF),
        state=st, regime=regime, months=months, score=score,
        method="Leak-free: inputs and band errors known by the end of " + keys[t] + " only; never re-run with later data.")


def summary(start="2022-11"):
    out = {}
    for h in (1, 3, 6, 12):
        n, gain, z, p, wins = dm(h, start, "tl_flat")
        keys, y, fx, tar = v2t.load_all()
        me, mn, cov = [], [], []
        for t in range(36, len(y) - h):
            if keys[t + h] < start:
                continue
            f = v2t.forecast(keys, y, fx, tar, t, h, P)
            b = v2t.band(keys, y, fx, tar, t, h, P)
            if f is None:
                continue
            me.append(abs(y[t + h] - f))
            mn.append(abs(y[t + h] - y[t]))
            if b:
                cov.append(f * b[0] <= y[t + h] <= f * b[1])
        out[str(h)] = dict(n=n, mae_model=round(sum(me) / len(me), 2), mae_naive=round(sum(mn) / len(mn), 2),
                           p_one_sided=round(p, 3), model_closer=wins,
                           band_coverage_pct=round(100 * sum(cov) / len(cov), 1))
    return dict(test_from=start, unit="USD/MWh", horizons=out)


def main():
    keys, y, fx, tar = v2t.load_all()
    tv = json.load(open(v2t.TARIFF))["series_version"]
    OUT.mkdir(parents=True, exist_ok=True)
    runs = []
    for t in range(len(keys)):
        if tar[t] is None or v2t.forecast(keys, y, fx, tar, t, 1, P) is None:
            continue
        if v2t.band_halfwidth(keys, y, fx, tar, t, 1, P) is None:
            continue
        json.dump(run_file(keys, y, fx, tar, t, tv), open(OUT / f"{keys[t]}.json", "w"), ensure_ascii=False)
        runs.append(keys[t])
    json.dump(dict(updated=keys[-1], engine_version=ENGINE_VERSION, tariff_series_version=tv,
                   path="outlook/snapshots/v2t/", months=runs, backtest=summary(),
                   note="One run per month from engine v2t, each with data known at that month only. "
                        "Regenerate all with: python3 engine/snapshots.py"),
              open(ROOT / "outlook" / "snapshots" / "index.json", "w"), ensure_ascii=False, indent=1)
    hist = json.load(open(ROOT / "engine" / "history" / "monthly_ptf.json"))
    json.dump(dict(updated=hist["fetched"], unit="USD/MWh", source="EPİAŞ PTF aylık ortalaması (engine/history/monthly_ptf.json)",
                   months=[dict(month=m["month"], ptf_usd_mwh=m["ptf_usd_mwh"], complete=m.get("complete", True))
                           for m in hist["months"] if m["month"] >= "2021-01"]),
              open(ROOT / "realized" / "monthly.json", "w"), ensure_ascii=False, indent=1)
    print(f"{len(runs)} runs: {runs[0]} .. {runs[-1]} | engine {ENGINE_VERSION} | tariff series {tv}")


if __name__ == "__main__":
    main()
