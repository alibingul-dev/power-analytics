"""Price Outlook Lab engine v2 (price-only core).

Leak-free by construction: forecast(y, t, h) only reads y[0..t] (months closed
by the end of month t). Units: USD/MWh. Parameters are re-estimated at every
as_of month from past data only.

Model, in log space:
  s(m)   smoothed seasonal profile: 2 harmonics fitted on log(price) minus its
         trailing 12-month mean, over the last `season_window` months.
  L_t    deseasonalised level = log y_t - s(month_t)
  L_t+h  = mu + phi**h * (L_t - mu), mu = mean of L over `level_window`
         months, phi = AR(1) slope of L over `phi_window` months, clipped.
  band   quantiles of past h-step log errors of this same model (25th/75th).
"""
import math
from baselines import load

P = dict(season_window=60, level_window=24, phi_window=60, phi_min=0.5, phi_max=0.99)


def _month(key):
    return int(key[5:])


def _solve(A, b):
    n = len(A)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        p = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[p] = M[p], M[c]
        if abs(M[c][c]) < 1e-12:
            return [0.0] * n
        for r in range(n):
            if r != c:
                f = M[r][c] / M[c][c]
                for k in range(c, n + 1):
                    M[r][k] -= f * M[c][k]
    return [M[i][n] / M[i][i] for i in range(n)]


def seasonal(keys, ly, t, window):
    rows = []
    for i in range(max(12, t - window + 1), t + 1):
        base = sum(ly[i - 12:i]) / 12
        m = _month(keys[i])
        w = 2 * math.pi * m / 12
        rows.append(([math.cos(w), math.sin(w), math.cos(2 * w), math.sin(2 * w)], ly[i] - base))
    if len(rows) < 24:
        return lambda m: 0.0
    A = [[sum(x[0][a] * x[0][b] for x in rows) for b in range(4)] for a in range(4)]
    b = [sum(x[0][a] * x[1] for x in rows) for a in range(4)]
    c = _solve(A, b)

    def s(m):
        w = 2 * math.pi * m / 12
        return c[0] * math.cos(w) + c[1] * math.sin(w) + c[2] * math.cos(2 * w) + c[3] * math.sin(2 * w)
    return s


def fit(keys, y, t, p=P):
    ly = [math.log(max(v, 0.5)) for v in y[: t + 1]]
    s = seasonal(keys, ly, t, p["season_window"])
    L = [ly[i] - s(_month(keys[i])) for i in range(t + 1)]
    lw = L[max(0, t - p["level_window"] + 1): t + 1]
    mu = sum(lw) / len(lw)
    seg = L[max(0, t - p["phi_window"] + 1): t + 1]
    x, z = [a - mu for a in seg[:-1]], [a - mu for a in seg[1:]]
    den = sum(a * a for a in x)
    phi = sum(a * b for a, b in zip(x, z)) / den if den else 0.9
    phi = min(p["phi_max"], max(p["phi_min"], phi))
    return dict(s=s, mu=mu, phi=phi, L=L[t])


def month_at(keys, t, h):
    m = _month(keys[t]) + h
    return (m - 1) % 12 + 1


def forecast(keys, y, t, h, p=P):
    f = fit(keys, y, t, p)
    L = f["mu"] + f["phi"] ** h * (f["L"] - f["mu"])
    return math.exp(L + f["s"](month_at(keys, t, h)))


def band(keys, y, t, h, p=P, lookback=48):
    """25th/75th percentile multipliers from this model's own past h-step errors (as of t)."""
    errs = []
    for u in range(max(36, t - lookback - h), t - h + 1):
        errs.append(math.log(max(y[u + h], 0.5)) - math.log(forecast(keys, y, u, h, p)))
    if len(errs) < 12:
        return None
    errs.sort()
    q = lambda a: errs[min(len(errs) - 1, max(0, int(round(a * (len(errs) - 1)))))]
    return math.exp(q(0.25)), math.exp(q(0.75))
