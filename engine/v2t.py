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
    if p.get("mu_stat") == "median":  # stress-test option, not the default
        sw = sorted(R[-p["mu_window"]:] if p.get("mu_window") else R)
        mu = sw[len(sw) // 2] if len(sw) % 2 else (sw[len(sw) // 2 - 1] + sw[len(sw) // 2]) / 2
    elif p.get("mu_stat") == "expanding":
        mu = sum(R) / len(R)
    if p.get("mu_fixed") is not None:  # stress-test option: hold the long-run ratio fixed
        mu = math.log(p["mu_fixed"])
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
        tariff_h = tar[t]
        if p["gas_path"] in ("april_trail", "april_restore"):  # opt-in tariff path, tested 2026-11-05
            for j in range(1, h + 1):
                if v2.month_at(keys, t, j) != 4:
                    continue
                if p["gas_path"] == "april_trail":
                    g = tar[t] / tar[t - 12] - 1 if t >= 12 and tar[t - 12] else 0.0
                else:
                    m = t
                    while m > 0 and tar[m - 1] is not None and tar[m - 1] >= tar[m] - 1e-9:
                        m -= 1  # back to the month of the last increase
                    fx_a = fx[t] * math.exp(drift * j)
                    g = max(0.0, (tar[m] / fx[m]) / (tariff_h / fx_a) - 1)
                tariff_h *= (1 + g)
        gh = gas_cost(tariff_h, fx[t] * math.exp(drift * h))
    return math.exp(Rf + s(v2.month_at(keys, t, h))) * gh


BAND_HALF_LIFE = 3  # months; chosen 2026-11-05 from 3/6/12 by 1-6 month coverage over 2022-11+
_FC = {}


def _fc(keys, y, fx, tar, u, h, p):
    k = (u, h, p["gas_path"], p["level_window"], p["min_hist"], len(y))
    if k not in _FC:
        _FC[k] = forecast(keys, y, fx, tar, u, h, p)
    return _FC[k]


def _abs_log_errs(keys, y, fx, tar, t, h, p):
    """(|log actual - log forecast|, weight) for h-step forecasts whose outcome was known by month t.

    Weight halves every BAND_HALF_LIFE months of age, so the band follows the current regime.
    """
    out = []
    for u in range(0, t - h + 1):
        f = _fc(keys, y, fx, tar, u, h, p)
        if f:
            age = t - (u + h)
            out.append((abs(math.log(max(y[u + h], 0.5)) - math.log(f)), 0.5 ** (age / BAND_HALF_LIFE)))
    return out


def _wmedian(pairs):
    pairs = sorted(pairs)
    tot = sum(w for _, w in pairs)
    acc = 0.0
    for v, w in pairs:
        acc += w
        if acc >= tot / 2:
            return v


def _median(v):
    return _wmedian([(x, 1.0) for x in v])


_HW = {}


def band_halfwidth(keys, y, fx, tar, t, h, p=P, min_err=8):
    """Non-decreasing in h: uncertainty cannot shrink with horizon (max of raw widths up to h)."""
    k = (t, h, p["gas_path"], min_err, len(y))
    if k not in _HW:
        raw = _raw_halfwidth(keys, y, fx, tar, t, h, p, min_err)
        prev = band_halfwidth(keys, y, fx, tar, t, h - 1, p, min_err) if h > 1 else None
        _HW[k] = raw if prev is None else (prev if raw is None else max(raw, prev))
    return _HW[k]


def _raw_halfwidth(keys, y, fx, tar, t, h, p=P, min_err=8):
    """Half-width in log space: decay-weighted median of past |log error| at horizon h.

    Symmetric around the point forecast, so the band always contains it (fix of 2026-11-05:
    the old 25th/75th error-quantile band could exclude the point when errors were one-sided,
    e.g. Sep-2026 in the Jan-2026 run). Only outcomes known by month t are used.
    With fewer than `min_err` errors at horizon h, the widest horizon that has enough
    is scaled by sqrt(h / h0).
    """
    e = _abs_log_errs(keys, y, fx, tar, t, h, p)
    if len(e) >= min_err:
        return _wmedian(e)
    for h0 in range(h - 1, 0, -1):
        e0 = _abs_log_errs(keys, y, fx, tar, t, h0, p)
        if len(e0) >= min_err:
            return _wmedian(e0) * math.sqrt(h / h0)
    return None


def band(keys, y, fx, tar, t, h, p=P, min_err=8):
    """(low, high) multipliers around the point forecast; ~50% of past outcomes inside."""
    w = band_halfwidth(keys, y, fx, tar, t, h, p, min_err)
    return None if w is None else (math.exp(-w), math.exp(w))
