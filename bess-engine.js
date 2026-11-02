/* BESS revenue engine for the power-analytics simulator.
   Pure functions, no DOM. Runs in the browser and in Node (tests).

   Units: power MW, energy MWh, prices TL/MWh, capacity prices TL/MW per hour.
   Hourly resolution, 24 hours per day (Türkiye has no DST).

   Dispatch: per-day dynamic programme over a discretised state of charge.
   - charging p MW for 1 h adds p * etaC MWh, discharging p MW removes p / etaD MWh
     (round-trip efficiency split evenly: etaC = etaD = sqrt(RTE))
   - every MWh discharged at the grid carries a throughput cost (degradation), so the
     optimiser only cycles when the spread pays for the wear
   - the day must end at the state it started (no free energy carried over)
   - a reserve block of R MW sold as PFK/SFK capacity keeps R MW of power headroom in
     both directions and an energy buffer on both sides of the SoC */
(function (root) {
  "use strict";

  function dayDispatch(price, o) {
    // o: {P, Emin, Emax, etaC, etaD, steps, wear, start, reserveMW, buffer}
    const n = o.steps, dE = (o.Emax - o.Emin) / n;
    const lo = o.Emin + (o.buffer || 0), hi = o.Emax - (o.buffer || 0);
    const pAvail = Math.max(0, o.P - (o.reserveMW || 0));
    const s0 = Math.round((o.start - o.Emin) / dE);
    const ok = i => { const e = o.Emin + i * dE; return e >= lo - 1e-9 && e <= hi + 1e-9; };
    const H = price.length, NEG = -1e18;
    let V = new Float64Array(n + 1).fill(NEG);
    V[s0] = 0;
    const back = [];
    for (let h = 0; h < H; h++) {
      const W = new Float64Array(n + 1).fill(NEG), from = new Int32Array(n + 1).fill(-1);
      const pr = price[h];
      for (let i = 0; i <= n; i++) {
        if (V[i] === NEG) continue;
        for (let j = 0; j <= n; j++) {
          if (!ok(j) && j !== i) continue;
          const de = (j - i) * dE;               // change of stored energy, MWh
          let grid;                               // + = sold to grid MWh, - = bought
          if (de > 0) { grid = -de / o.etaC; if (-grid > pAvail + 1e-9) continue; }
          else if (de < 0) { grid = -de * o.etaD; if (grid > pAvail + 1e-9) continue; }
          else grid = 0;
          const v = V[i] + grid * pr - (grid > 0 ? grid * o.wear : 0);
          if (v > W[j]) { W[j] = v; from[j] = i; }
        }
      }
      back.push(from); V = W;
    }
    const end = s0;
    if (V[end] === NEG) return null;
    const soc = new Array(H + 1), grid = new Array(H);
    let s = end; soc[H] = o.Emin + s * dE;
    for (let h = H - 1; h >= 0; h--) {
      const p = back[h][s];
      const de = (s - p) * dE;
      grid[h] = de > 0 ? -de / o.etaC : de < 0 ? -de * o.etaD : 0;
      s = p; soc[h] = o.Emin + s * dE;
    }
    return { value: V[end], grid, soc };
  }

  // A day's price line for a market; GİP hours without trade fall back to that hour's PTF.
  // Returns null when the day is not usable (missing PTF hours).
  function series(day, field) {
    const ptf = day && day.ptf;
    if (!ptf || ptf.length !== 24 || ptf.some(v => v == null)) return null;
    const s = day[field];
    if (!s || s.length !== 24) return null;
    return s.map((v, h) => (v == null ? ptf[h] : v));
  }

  // Forecast used by the realistic case: yesterday's prices (persistence), a standard naive benchmark.
  function persistence(days, i, field) { return series(i > 0 ? days[i - 1] : days[i], field) || series(days[i], field); }

  function settle(grid, price) { let c = 0; for (let h = 0; h < grid.length; h++) c += grid[h] * price[h]; return c; }

  /* Simulate one strategy over all days.
     strat: {market: "dam"|"idm", reserve: 0..P MW, service: "pfk"|"sfk"|null, foresight: "perfect"|"persistence"}
     batt:  {P, E, rte, socMin, socMax, wearTLperMWh, steps}
     rules: {pfkRatio, sfkRatio} required MWh per MW of reserve (TEİAŞ criteria), kept half on each side of the SoC */
  function simulate(days, strat, batt, rules) {
    const eta = Math.sqrt(batt.rte), Emin = batt.E * batt.socMin, Emax = batt.E * batt.socMax;
    const usable = Emax - Emin;
    const ratio = strat.service === "sfk" ? rules.sfkRatio : rules.pfkRatio;
    let R = strat.service ? Math.min(strat.reserve, batt.P, usable / ratio) : 0;
    const buffer = R * ratio / 2;   // required energy split evenly: stored for up-regulation, headroom for down-regulation
    const field = strat.market === "idm" ? "gip" : "ptf";
    const start = (Emin + Emax) / 2;
    const out = [];
    for (let i = 0; i < days.length; i++) {
      const d = days[i];
      const actual = series(d, field);
      if (!actual) continue;
      const plan = strat.foresight === "persistence" ? persistence(days, i, field) : actual;
      let arb = 0, throughput = 0, dispatch = null;
      if (actual && plan && R < batt.P) {
        dispatch = dayDispatch(plan, { P: batt.P, Emin, Emax, etaC: eta, etaD: eta, steps: batt.steps || 20,
          wear: batt.wearTLperMWh, start, reserveMW: R, buffer: R ? buffer : 0 });
        if (dispatch) {
          arb = settle(dispatch.grid, actual);
          for (const g of dispatch.grid) if (g > 0) throughput += g;
        }
      }
      let cap = 0;
      if (R && strat.service) { const cp = d[strat.service] || []; for (const v of cp) cap += (v || 0) * R; }
      const wear = throughput * batt.wearTLperMWh;
      out.push({ date: d.date, arb, cap, wear, net: arb + cap - wear, throughput, R, dispatch });
    }
    return out;
  }

  function summarise(res, batt) {
    const n = res.length || 1, k = 365 / n;
    const sum = f => res.reduce((a, r) => a + r[f], 0);
    const arb = sum("arb"), cap = sum("cap"), wear = sum("wear"), net = sum("net"), thr = sum("throughput");
    return {
      days: res.length,
      annual: { arb: arb * k, cap: cap * k, wear: wear * k, net: net * k },
      perMWyr: net * k / batt.P,
      cyclesPerYear: thr * k / ((batt.socMax - batt.socMin) * batt.E),
      reserveMW: res.length ? res[res.length - 1].R : 0,
    };
  }

  /* Project finance on an annual revenue line.
     f: {capexPerKWh (TL), fixedOMpct (of capex/yr), years, wacc, tax, deprYears, degrPerYear, augment: bool} */
  function finance(netYear1, batt, f) {
    const capex = f.capexPerKWh * batt.E * 1000;
    const flows = [-capex]; let cum = -capex, payback = null;
    for (let y = 1; y <= f.years; y++) {
      const fade = f.augment ? 1 : Math.pow(1 - f.degrPerYear, y - 1);
      const rev = netYear1 * fade;
      const om = capex * f.fixedOMpct;
      const depr = y <= f.deprYears ? capex / f.deprYears : 0;
      const aug = f.augment ? capex * f.augmentPctPerYear : 0;
      const ebit = rev - om - aug - depr;
      const tax = Math.max(0, ebit) * f.tax;
      const cf = rev - om - aug - tax;
      const prev = cum; flows.push(cf); cum += cf;
      if (payback === null && cum >= 0 && cf > 0) payback = y - 1 + (-prev) / cf;
    }
    const npv = flows.reduce((a, c, t) => a + c / Math.pow(1 + f.wacc, t), 0);
    return { capex, flows, npv, irr: irr(flows), payback };
  }

  function irr(flows) {
    let lo = -0.99, hi = 1.5;
    const f = r => flows.reduce((a, c, t) => a + c / Math.pow(1 + r, t), 0);
    if (f(lo) * f(hi) > 0) return null;
    for (let i = 0; i < 200; i++) { const m = (lo + hi) / 2; (f(lo) * f(m) <= 0) ? (hi = m) : (lo = m); }
    return (lo + hi) / 2;
  }

  const api = { dayDispatch, simulate, summarise, finance, irr };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.BESS = api;
})(typeof self !== "undefined" ? self : this);
