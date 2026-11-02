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
    // o: {P, Emin, Emax, etaC, etaD, steps, wear, start, reserveMW, bufLo, bufHi}
    // wear is charged per MWh taken out of storage (before discharge losses)
    const n = o.steps, dE = (o.Emax - o.Emin) / n;
    const lo = o.Emin + (o.bufLo || 0), hi = o.Emax - (o.bufHi || 0);
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
          const v = V[i] + grid * pr - (de < 0 ? -de * o.wear : 0);
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
  // Never falls back to the day's own prices: a day without a usable previous day is skipped in this mode.
  function persistence(days, i, field) { return i > 0 ? series(days[i - 1], field) : null; }

  function settle(grid, price) { let c = 0; for (let h = 0; h < grid.length; h++) c += grid[h] * price[h]; return c; }

  /* Simulate one strategy over all days.
     strat: {market: "dam"|"idm", reserve: 0..P MW, service: "pfk"|"sfk"|null, foresight: "perfect"|"persistence"}
     batt:  {P, E, rte, socMin, socMax, wearTLperMWh, steps}
     rules: {pfkRatio, sfkRatio} required MWh per MW of reserve (TEİAŞ criteria), kept half on each side of the SoC */
  function simulate(days, strat, batt, rules) {
    const eta = Math.sqrt(batt.rte), Emin = batt.E * batt.socMin, Emax = batt.E * batt.socMax;
    const usable = Emax - Emin;
    const ratio = strat.service === "sfk" ? rules.sfkRatio : rules.pfkRatio;
    // Required energy = ratio x R (grid MWh), half deliverable upward and half absorbable downward.
    // Upward side needs /etaD of stored energy, downward side needs *etaC of empty space.
    const need = r => r * ratio / 2 / eta + r * ratio / 2 * eta;
    let R = strat.service ? Math.min(strat.reserve, batt.P) : 0;
    if (R && need(R) > usable) R = usable / need(1);
    const bufLo = R * ratio / 2 / eta, bufHi = R * ratio / 2 * eta;
    const field = strat.market === "idm" ? "gip" : "ptf";
    const start = (Emin + Emax) / 2;
    const out = [];
    for (let i = 0; i < days.length; i++) {
      const d = days[i];
      const actual = series(d, field);
      if (!actual) continue;
      const plan = strat.foresight === "persistence" ? persistence(days, i, field) : actual;
      if (!plan && R < batt.P) continue;
      // wear in TL: per-day FX when the data carries it, so a USD cell cost is priced at that day's rate
      const wearTL = batt.wearUSDperMWh != null && d.fx ? batt.wearUSDperMWh * d.fx : batt.wearTLperMWh;
      let arb = 0, throughput = 0, dispatch = null;
      if (plan && R < batt.P) {
        dispatch = dayDispatch(plan, { P: batt.P, Emin, Emax, etaC: eta, etaD: eta, steps: batt.steps || 48,
          wear: wearTL, start, reserveMW: R, bufLo, bufHi });
        if (dispatch) {
          arb = settle(dispatch.grid, actual);
          for (let h = 0; h < 24; h++) if (dispatch.soc[h + 1] < dispatch.soc[h]) throughput += dispatch.soc[h] - dispatch.soc[h + 1];
        }
      }
      let cap = 0;
      if (R && strat.service) { const cp = d[strat.service] || []; for (const v of cp) cap += (v || 0) * R; }
      const wear = throughput * wearTL;
      out.push({ date: d.date, fx: d.fx || null, arb, cap, wear, net: arb + cap - wear, throughput, R, dispatch });
    }
    return out;
  }

  function summarise(res, batt) {
    const n = res.length || 1, k = 365 / n;
    const sum = f => res.reduce((a, r) => a + r[f], 0);
    const arb = sum("arb"), cap = sum("cap"), wear = sum("wear"), net = sum("net"), thr = sum("throughput");
    const usd = (f, fx) => res.reduce((a, r) => a + r[f] / (r.fx || fx), 0) * k;
    return {
      usd: fx => ({ arb: usd("arb", fx), cap: usd("cap", fx), wear: usd("wear", fx), net: usd("net", fx) }),
      fxDaily: res.length > 0 && res.every(r => r.fx),
      days: res.length,
      annual: { arb: arb * k, cap: cap * k, wear: wear * k, net: net * k },
      perMWyr: net * k / batt.P,
      cyclesPerYear: thr * k / ((batt.socMax - batt.socMin) * batt.E),   // storage-side discharge / usable energy
      reserveMW: res.length ? res[res.length - 1].R : 0,
    };
  }

  /* Project finance on an annual revenue line.
     f: {capexPerKWh (TL), fixedOMpct (of capex/yr), years, wacc, tax, deprYears, degrPerYear, augment: bool} */
  function finance(netYear1, batt, f) {
    const capex = f.capexPerKWh * batt.E * 1000;
    const flows = [-capex]; let cum = -capex, payback = null;
    const losses = [];   // tax losses carried forward up to lossYears (Türkiye: 5 years, KVK Md. 9)
    const lossYears = f.lossYears == null ? 5 : f.lossYears, augPct = f.augmentPctPerYear || 0;
    for (let y = 1; y <= f.years; y++) {
      const fade = f.augment ? 1 : Math.pow(1 - f.degrPerYear, y - 1);
      const rev = netYear1 * fade;
      const om = capex * f.fixedOMpct;
      const depr = y <= f.deprYears ? capex / f.deprYears : 0;
      const aug = f.augment ? capex * augPct : 0;
      const ebit = rev - om - aug - depr;
      let taxable = ebit;
      if (taxable < 0) losses.push({ y, amt: -taxable });
      else {
        for (const l of losses) { if (y - l.y > lossYears || !l.amt) continue; const u = Math.min(l.amt, taxable); l.amt -= u; taxable -= u; }
      }
      const tax = Math.max(0, taxable) * f.tax;
      const cf = rev - om - aug - tax;
      const prev = cum; flows.push(cf); cum += cf;
      if (payback === null && cum >= 0 && cf > 0) payback = y - 1 + (-prev) / cf;
    }
    const npv = flows.reduce((a, c, t) => a + c / Math.pow(1 + f.wacc, t), 0);
    return { capex, flows, npv, irr: irr(flows), payback };
  }

  function irr(flows) {
    let lo = -0.99, hi = 10;
    const f = r => flows.reduce((a, c, t) => a + c / Math.pow(1 + r, t), 0);
    if (f(lo) * f(hi) > 0) return null;
    for (let i = 0; i < 200; i++) { const m = (lo + hi) / 2; (f(lo) * f(m) <= 0) ? (hi = m) : (lo = m); }
    return (lo + hi) / 2;
  }

  const api = { dayDispatch, simulate, summarise, finance, irr };
  if (typeof module !== "undefined" && module.exports) module.exports = api; else root.BESS = api;
})(typeof self !== "undefined" ? self : this);
