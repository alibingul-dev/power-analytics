/* Assumptions and references for the BESS Investment Simulator.
   Every default value below comes from a public source listed in REFS (1-based index).
   Where a value is derived (a calculation on sourced numbers) the note says how. */
(function (root) {
  "use strict";
  const REFS = [
    /* 1 */ { publisher: "NREL", title: "Annual Technology Baseline 2025: Utility-Scale Battery Storage", year: 2025, where: "cost and performance assumptions", url: "https://atb.nlr.gov/electricity/2025/utility-scale_battery_storage" },
    /* 2 */ { publisher: "NREL", title: "Cost Projections for Utility-Scale Battery Storage: 2025 Update (NREL/TP-6A40-93281)", year: 2025, where: "Table 2; p.6 energy/power cost split; p.11 efficiency", url: "https://docs.nrel.gov/docs/fy25osti/93281.pdf" },
    /* 3 */ { publisher: "Lazard", title: "Levelized Cost of Energy+ (LCOS v11.0)", year: 2026, where: "pp.37–38, storage cost and operating assumptions", url: "https://www.lazard.com/media/kcfconhf/lazards-lcoeplus_vf.pdf" },
    /* 4 */ { publisher: "BloombergNEF via Energy-Storage.News", title: "Energy Storage System Cost Survey 2025 (turnkey prices by region)", year: 2025, where: "December 2025 coverage", url: "https://www.energy-storage.news/?p=92133" },
    /* 5 */ { publisher: "Ember", title: "Battery storage costs (all-in capex outside China and the US)", year: 2025, where: "December 2025", url: "https://ember-energy.org/?p=17718" },
    /* 6 */ { publisher: "Modo Energy", title: "UK & Europe model assumptions (battery state of health by cycles)", year: 2026, where: "July 2026", url: "https://docs.modoenergy.com/pages/jul-2026/uk-europe/model-assumptions/" },
    /* 7 */ { publisher: "PNNL", title: "Energy Storage Grand Challenge Cost and Performance Assessment 2022 (PNNL-33283)", year: 2022, where: "Tables 4.2–4.3", url: "https://www.pnnl.gov/sites/default/files/media/file/ESGC%20Cost%20Performance%20Report%202022%20PNNL-33283.pdf" },
    /* 8 */ { publisher: "A. Fletcher, submission citing GHD (2025)", title: "Draft 2025–26 GenCost consultation submission (battery degradation per year)", year: 2025, where: "degradation table", url: "https://www.griffith.edu.au/__data/assets/pdf_file/0031/2257519/Andrew-Fletcher-Draft-2025-2026-GenCost-Consultation-Submission.pdf" },
    /* 9 */ { publisher: "Federal Reserve Bank of St. Louis (FRED)", title: "Market Yield on U.S. Treasury Securities at 10-Year Constant Maturity (DGS10)", year: 2026, where: "29 Oct 2026: 4.98%", url: "https://fred.stlouisfed.org/graph/?g=1q06w" },
    /* 10 */ { publisher: "A. Damodaran, NYU Stern", title: "Country Default Spreads and Risk Premiums (Turkey)", year: 2026, where: "January 2026 update: total equity risk premium 8.89%, USD", url: "https://pages.stern.nyu.edu/~adamodar/New_Home_Page/datafile/ctryprem.html" },
    /* 11 */ { publisher: "PwC Türkiye", title: "Kurumlar vergisi oranı", year: 2026, where: "17 Feb 2026: 25%", url: "https://www.pwc.com.tr/tr/hizmetlerimiz/vergi/vergi-portali/pratik-bilgiler/oranlar/kurumlar-vergisi-orani.html" },
    /* 12 */ { publisher: "Gelir İdaresi (copy by Alomaliye)", title: "Amortismana tabi iktisadi kıymetlerin faydalı ömür listesi", year: null, where: "line 3.14.7 Akümülatörler: 5 years", url: "https://alomaliye.com/wp-content/uploads/2018/02/faydal%C4%B1-omur-amortisman_listesi-.pdf" },
    /* 13 */ { publisher: "TCMB", title: "Gösterge niteliğindeki döviz kurları", year: 2026, where: "30 Oct 2026, USD buying 49.7747", url: "https://www.tcmb.gov.tr/kurlar/today.xml" },
    /* 14 */ { publisher: "Elektrik Piyasası Yan Hizmetler Yönetmeliği (consolidated copy by Alomaliye)", title: "Primer ve sekonder frekans kontrolü: fiyatlama ve ödeme, Md. 18–19, 26–28", year: 2026, where: "consolidated to 09.04.2026", url: "https://www.alomaliye.com/wp-content/uploads/2017/11/elektrik-piyas-yan-09-04-2026.pdf" },
    /* 15 */ { publisher: "Ratio Energy", title: "Türkiye'de bataryalar ile PFK katılımı", year: 2025, where: "energy/reserve ratio 1.25, SoC management methods", url: "https://www.ratio.energy/knowledge-hub/turkiye-de-bataryalar-ile-pfk-katilimi" },
    /* 16 */ { publisher: "Elektrik Tesisat Portalı", title: "Elektrik depolama tesislerinin şebeke bağlantısı ve SCADA teknik kriterleri", year: 2021, where: "PFK ≥ 1.25; SFK 6.75 / 9 / 11.25 for 3 / 4 / 5-hour blocks", url: "https://www.elektriktesisatportali.com/elektrik-depolama-tesislerinin-sebeke-baglantisi-scada-teknik-kriterleri-yayinlandi.html" },
    /* 17 */ { publisher: "TEİAŞ", title: "Elektrik depolama tesislerine ait usul, esas ve teknik kriterler hakkında duyuru", year: 2026, where: "criteria reissued 03.07.2026", url: "https://www.teias.gov.tr/duyurular/elektrik-depolama-tesislerine-ait-usul-esas-ve-teknik-kriterler-hakkinda-duyuru" },
    /* 18 */ { publisher: "Elektrik Piyasasında Depolama Faaliyetleri Yönetmeliği (Lexpera)", title: "Consolidated text", year: 2026, where: "Md. 5 and 7: standalone and plant-paired storage, market participation", url: "https://www.lexpera.com.tr/mevzuat/yonetmelikler/elektrik-piyasasinda-depolama-faaliyetleri-yonetmeligi-2" },
    /* 19 */ { publisher: "EPDK Kurul Kararı 14030 (Lexpera)", title: "Dengesizlik fiyatı katsayıları, 01.01.2026'dan itibaren", year: 2025, where: "11.12.2025", url: "https://www.lexpera.com.tr/resmi-gazete/metin/enerji-piyasasi-duzenleme-kurulunun-11-12-2025-tarihli-ve-14030-sayili-karari-33122" },
    /* 20 */ { publisher: "Karar.com", title: "GÖP ve DGP azami fiyat limiti 4.500 TL/MWh (EPDK 14459)", year: 2026, where: "in force 04.04.2026", url: "https://www.karar.com/ekonomi-haberleri/enerji-piyasasinda-savas-etkisi-tavan-fiyat-4-500-tlye-cikti-epiastan-2039815" },
    /* 21 */ { publisher: "EPİAŞ", title: "Şeffaflık Platformu teknik dokümanı (electricity-service)", year: 2026, where: "market prices, GİP AOF, ancillary capacity prices and amounts", url: "https://seffaflik.epias.com.tr/electricity-service/technical/tr/index.html" },
    /* 22 */ { publisher: "Ember", title: "Türkiye: depolama", year: 2026, where: "installed and licensed storage, February 2026", url: "https://ember-energy.org/tr/chapter/depolama/" },
    /* 23 */ { publisher: "NREL", title: "Annual Technology Baseline 2024: Utility-Scale Battery Storage", year: 2024, where: "O&M: 2.5% of capex, augmentation not included", url: "https://atb.nrel.gov/electricity/2024/utility-scale_battery_storage" },
    /* 25 */ { publisher: "Alomaliye", title: "Kurumlar vergisi yönünden zarar mahsubu (KVK Md. 9)", year: 2024, where: "losses carried forward for 5 years", url: "https://www.alomaliye.com/2024/03/12/kurumlar-vergisi-yonunden-zarar-mahsubu/" },
    /* 24 */ { publisher: "BloombergNEF", title: "Lithium-ion battery pack prices fall to $108 per kilowatt-hour", year: 2025, where: "December 2025 battery price survey", url: "https://about.bnef.com/insights/clean-energy/lithium-ion-battery-pack-prices-fall-to-108-per-kilowatt-hour" },
  ];

  const A = {
    rte:   { name: "Round-trip efficiency", value: 0.85, label: "85% (AC to AC, includes cooling and controls)", refs: [1, 2],
             note: "NREL ATB 2025 and NREL 2025 cost update. Lazard 2026 gives 86–92% before auxiliaries; 85% is the only figure stated to include them." },
    dod:   { name: "Usable state of charge", value: 0.90, label: "90% (5–95% window)", refs: [3],
             note: "Lazard LCOS v11.0 assumes 90% depth of discharge in all cases." },
    capex: { name: "Installed cost", value: 177, label: "$177/kWh for a 4-hour system, scaled by duration", refs: [4, 5, 2],
             note: "BNEF 2025 turnkey price for Europe. Range: Ember $125 (all-in outside China/US) to NREL 2026 mid $308. Shorter systems cost more per kWh: scaled with NREL's split of $241/kWh energy + $372/kW power. Turkish customs and grid connection are not included (no public source found)." },
    om:    { name: "Fixed O&M", value: 0.025, label: "2.5% of capex per year, excluding augmentation", refs: [23, 1],
             note: "NREL ATB 2024: 2.5% of capex without augmentation. ATB 2025 moved to 4% because it folds augmentation in; here augmentation is paid through the wear cost instead, in proportion to how hard the battery is cycled, so 2.5% avoids counting it twice." },
    deg:   { name: "Capacity fade", value: 0.0, label: "0%/yr (lost capacity is bought back through the wear cost)", refs: [6, 8],
             note: "The wear cost replaces the capacity each MWh uses up, so nameplate energy is held. Setting fade above 0 models a battery that is never topped up: the investment case then drops the wear cost and applies the fade instead (GHD 2025: about 1.6%/yr)." },
    pack:  { name: "Replacement cell cost", value: 108, label: "$108/kWh (battery pack, 2025)", refs: [24],
             note: "BNEF 2025 average lithium-ion pack price. Used only to price the capacity a cycle wears out." },
    cyc:   { name: "Cycle life", value: 5000, soh: 0.79, label: "5,000 full cycles to 79% health", refs: [6, 7],
             note: "Modo (July 2026): state of health 79% after 5,000 equivalent full cycles. Wear cost per MWh discharged = cell cost × 21% ÷ 5,000 cycles ÷ usable share; at defaults about $5/MWh. The optimiser only trades when the spread beats this. PNNL counts to 60% health, which gives longer lives." },
    life:  { name: "Project life", value: 15, label: "15 years", refs: [1, 3],
             note: "NREL ATB uses 15 years; Lazard uses 20 with augmentation." },
    wacc:  { name: "Discount rate", value: 0.139, label: "13.9% (USD, all-equity)", refs: [9, 10],
             note: "US 10-year Treasury 4.98% (FRED, 29 Oct 2026) + Damodaran's total equity risk premium for Turkey 8.89% (January 2026). Revenue is held flat in USD, so this nominal rate is a conservative choice." },
    tax:   { name: "Corporate tax", value: 0.25, label: "25%, losses carried forward 5 years", refs: [11, 25], note: "Kurumlar vergisi oranı, 2026. Tax losses offset profits of the next 5 years (KVK Md. 9)." },
    depr:  { name: "Tax depreciation", value: 5, label: "5 years, straight line", refs: [12],
             note: "Faydalı ömür listesi line 3.14.7 (akümülatörler). There is no separate line for grid-scale battery systems." },
    fx:    { name: "USD/TRY", value: 49.77, label: "49.77 (TCMB, 30 Oct 2026)", refs: [13],
             note: "Each day's TL revenue converts at that day's TCMB rate when the data carries it; this spot rate is the fallback and prices the wear cost in the investment inputs." },
    ratio: { name: "Reserve energy rules", value: { pfk: 1.25, sfk: 2.25 },
             label: "PFK: 1.25 MWh per MW offered; SFK: 2.25 MWh per MW (1-hour block); held half above, half below the state of charge", refs: [15, 16, 17, 14],
             note: "PFK 1.25, split half as stored energy and half as charging headroom, from Ratio Energy and summaries of the TEİAŞ criteria; the 03.07.2026 reissue could not be opened, so treat as provisional. SFK 2.25 is derived, not published: sources give 6.75 / 9 / 11.25 for 3 / 4 / 5-hour blocks (hours × 2 directions × 1.125); 2.25 is the 1-hour case, matching hourly capacity prices. Both services pay reserve MW × hourly capacity price (Yan Hizmetler Md. 18–19, 26–27); penalties for non-delivery are not modelled." },
  };

  const METHOD =
    "<p><b>Dispatch.</b> Each day is optimised separately with dynamic programming over the battery's state of charge (hourly steps). " +
    "The battery buys and sells in the chosen market (GÖP day-ahead price or GİP weighted average price), cannot exceed its power or usable energy, " +
    "loses energy as set by the round-trip efficiency (split evenly between charging and discharging) and ends each day where it started, at the middle of the usable range. The state of charge is split into 32–96 levels depending on duration (a modelling choice, not a sourced value).</p>" +
    "<p><b>Price knowledge.</b> 'Perfect foresight' plans each day on that day's actual prices, the theoretical maximum. " +
    "'Plan on yesterday's prices' makes the plan with the previous day's prices and settles it at the actual prices: a simple, reproducible benchmark (persistence forecast). Days without a usable previous day are left out, never filled with the day's own prices. Real desks land between the two.</p>" +
    "<p><b>Battery wear.</b> Every MWh discharged is charged the cost of buying back the capacity it wears out: cell price × capacity lost over the cycle life ÷ cycle life. The optimiser only cycles when the spread pays for this, and it is shown as a cost line. Fixed O&M excludes augmentation so the two are not counted twice.</p>" +
    "<p><b>Reserves.</b> The MW offered as PFK or SFK earns that hour's published capacity price for every hour. The same MW of power is held back from trading and the required energy (ratio × MW) is kept half above and half below the state of charge. " +
    "Revenue assumes every offer is accepted at the published price. If the energy rule does not allow the MW asked for, the reserve is cut to what fits and the page shows the MW actually used. When the offer is above 15% of what TEİAŞ procures on average, the page warns that the real price would likely be lower (15% is our rule of thumb, not a sourced value).</p>" +
    "<p><b>Year 1 and the project.</b> The last 365 days are scaled to a year. Each day's net revenue (after wear) is converted to USD at that day's TCMB rate, and year 1 is held flat over the project life, " +
    "reduced by capacity fade if set. Cash flow = revenue − fixed O&M − tax; tax uses straight-line depreciation, and tax losses are carried forward for up to 5 years. NPV and IRR are in USD.</p>" +
    "<p><b>Not modelled.</b> Grid connection and transmission charges, imbalance penalties, reserve non-delivery penalties, financing structure, Turkish customs, " +
    "inflation and FX changes. These are left out because no public source was found that fixes them for a standalone battery in 2026.</p>";

  const DATA = "Hourly prices from the EPİAŞ Transparency Platform [21]: day-ahead price (PTF), system marginal price (SMF), positive and negative imbalance prices, intraday weighted average price (GİP AOF), " +
    "primary and secondary frequency reserve capacity prices and the amounts TEİAŞ procured. Refreshed every night for the last 365 complete days. " +
    "Context: about 208 MW of storage paired with plants was in operation in February 2026 [22]; storage rules follow the Depolama Faaliyetleri Yönetmeliği [18]; " +
    "imbalance coefficients follow EPDK Decision 14030 [19]; the day-ahead price cap is 4,500 TL/MWh [20].";

  // Cost per kWh for a given duration, from a 4-hour reference price, using NREL's energy/power split [2].
  function capexFor(hours, ref4h) {
    const e = 241, p = 372;
    return ref4h * (e + p / hours) / (e + p / 4);
  }

  root.BESS_SOURCES = { refs: REFS, assumptions: A, method: METHOD, data: DATA, capexFor };
})(typeof self !== "undefined" ? self : this);
