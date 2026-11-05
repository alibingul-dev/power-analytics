"""Price Outlook Lab engine v2t — v2 plus the gas-cost driver (BOTAŞ power tariff).

Leak-free: forecast(..., t, h) reads only months 0..t of price, FX and tariff.
The tariff for month t+1 is NOT assumed known at the end of month t.
Units: price and gas cost in USD/MWh, tariff in TL/1000 Sm3, FX in TRY per USD.

Gas cost of a CCGT MWh:  G_t = tariff_t / 10.64 / 0.52 / fx_t
  10.64 MWh per 1000 Sm3 (BOTAŞ conversion), 0.52 = assumed CCGT efficiency.

Model, in log space:
  s(m)   seasonal profile of log price (same as v2, fitted on price history to t).
  R_t    log(price_t / G_t) - s(month_t)   (deseasonalised spark ratio)
  R_t+h  = mu + phi**h * (R_t - mu); mu = mean of R over the last `level_window`
         months with a tariff, phi = AR(1) slope of R, clipped.
  G_t+h  per `gas_path`:
         "usd_flat"  G stays at G_t in USD (tariff follows the lira)
         "tl_flat"   tariff stays in TL, FX drifts at its trailing 12-month pace
  price  = exp(R_t+h + s(month_t+h)) * G_t+h
"""
import json
import math
from pathlib import Path

import v2
from baselines import load

TARIFF = Path(__file__).parent / "history" / "botas_power_tariff.json"
MWH_PER_KSM3 = 10.64
EFF = 0.52
P = dict(level_window=24, min_hist=6, phi_min=0.3, phi_max=0.95, gas_path="usd_flat")


def load_all():
    keys, y = load()
    m = json.load(open(Path(__file__).parent / "history" / "monthly_ptf.json"))["months"]
    fx = {x["month"]: x["usdtry_implied"] for x in m}
    tar = json.load(open(TARIFF))["months"]
    tariff = [tar.get(k, {}).get("tl_per_1000sm3") for k in keys]
    return keys, y, [fx[k] for k in keys], tariff


def gas_cost(tariff, fx):
    return tariff / MWH_PER_KSM3 / EFF / fx


def forecast(keys, y, fx, tar, t, h, p=P):
    if tar[t] is None:
        return None
    ly = [math.log(max(v, 0.5)) for v in y[: t + 1]]
    s = v2.seasonal(keys, ly, t, v2.P["season_window"])
    R = []
    for i in range(t + 1):
        if tar[i] is None:
            continue
        g = gas_cost(tar[i], fx[i])
        R.append(ly[i] - math.log(g) - s(v2._month(keys[i])))
    if len(R) < p["min_hist"]:
        return None
    win = R[-p["level_window"]:]
    mu = sum(win) / len(win)
    x, z = [a - mu for a in win[:-1]], [a - mu for a in win[1:]]
    den = sum(a * a for a in x)
    phi = sum(a * b for a, b in zip(x, z)) / den if den else 0.8
    phi = min(p["phi_max"], max(p["phi_min"], phi))
    Rf = mu + phi ** h * (R[-1] - mu)
    g0 = gas_cost(tar[t], fx[t])
    if p["gas_path"] == "usd_flat":
        gh = g0
    else:
        k = max(0, t - 12)
        drift = (math.log(fx[t]) - math.log(fx[k])) / (t - k) if t > k else 0.0
        gh = gas_cost(tar[t], fx[t] * math.exp(drift * h))
    return math.exp(Rf + s(v2.month_at(keys, t, h))) * gh


def band(keys, y, fx, tar, t, h, p=P, lookback=36, min_err=8):
    """25th/75th percentile multipliers from this model's own past h-step errors (as of t)."""
    errs = []
    for u in range(max(0, t - lookback - h), t - h + 1):
        f = forecast(keys, y, fx, tar, u, h, p)
        if f:
            errs.append(math.log(max(y[u + h], 0.5)) - math.log(f))
    if len(errs) < min_err:
        return None
    errs.sort()
    q = lambda a: errs[min(len(errs) - 1, max(0, int(round(a * (len(errs) - 1)))))]
    return math.exp(q(0.25)), math.exp(q(0.75))
