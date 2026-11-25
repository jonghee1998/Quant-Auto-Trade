# Market-condition indicators for a "lose little, keep upside" US equity app

Scope note: ~20 tool calls. Facts below carry inline sources. Statements marked "(unverified)" are background knowledge I could not confirm in this session and belong with Gaps; the report writer should not present them as sourced.

## 1. Market breadth (% above 200-DMA, A/D line, new highs/lows)

### Takeaway
Breadth is mostly practitioner lore. Rules exist (the Zweig Breadth Thrust, "% above 200-DMA" bands), but I found no peer-reviewed evidence that breadth reduces drawdowns beyond the index's own trend filter. Its signals are rare, and free constituent-level data is hard to get. Use it as context on the dashboard, not as a trigger.

### Cited Findings
- Zweig Breadth Thrust: the 10-day EMA of NYSE Advances/(Advances+Declines) moves from below 0.40 to above 0.615 within 10 days. It is a bullish (risk-on re-entry) signal, not a risk-off one — [StockCharts, Arthur Hill](https://articles.stockcharts.com/article/articles-arthurhill-2019-01-perspective---40-years-of-the-zweig-breadth-thrust---weight-of-the-evidence/)
- The NYSE ZBT produced only 8 signals in about 40 years. The Nasdaq version had 3 and did not exceed 0.615 from 1992 to 2010. After the October 2015 signal, the NY Composite still made a new low. The author says "some tweaking is needed" — [StockCharts](https://articles.stockcharts.com/article/articles-arthurhill-2019-01-perspective---40-years-of-the-zweig-breadth-thrust---weight-of-the-evidence/)
- NYSE-only breadth misses Nasdaq-listed names, which make up about 26% of the S&P 500 and about 53% of the S&P 600 — [StockCharts](https://articles.stockcharts.com/article/articles-arthurhill-2019-01-perspective---40-years-of-the-zweig-breadth-thrust---weight-of-the-evidence/)
- Practitioners combine many breadth gauges. Hill watches nine, including High-Low Percent and % above 200-day EMA, and wants 5 of 9 to turn bullish before calling the market bullish. One cited low reading was "just 30%" of S&P 500 stocks above their 200-day EMA — [StockCharts](https://articles.stockcharts.com/article/articles-arthurhill-2019-01-perspective---40-years-of-the-zweig-breadth-thrust---weight-of-the-evidence/)
- The CNN Fear & Greed index uses two breadth inputs: NYSE 52-week highs vs lows, and up-volume vs down-volume — [CFI](https://corporatefinanceinstitute.com/resources/capital_markets/fear-and-greed-index/)

### Inferences
- Common practitioner bands for % of S&P 500 stocks above their 200-DMA: >70% is broad and healthy (or overbought), 50% is the midline, and <30% is washed out or oversold. These are conventions, not tested thresholds. Only the 30% "weak" reading is cited above.
- The app can compute breadth itself from constituent daily closes (e.g., about 500 tickers over a free or cheap price API). That route is more robust than scraping NYSE A/D data, which has no clean free API.
- Useful role: confirmation or divergence. Narrowing breadth while the index makes new highs is a caution flag. Present it as context, not as a sell rule.

### Gaps
- I found no rigorous study of drawdown reduction from %>200-DMA or A/D-line rules.
- I found no free official API for NYSE advance/decline or new high/low counts. StockCharts symbols such as $SPXA200R are behind its site (unverified).
- ZBT forward-return statistics were not in the fetched source.

## 2. Credit spreads, yield curve, VIX & term structure, Fear & Greed, NFCI

### Takeaway
Credit spreads (HY OAS) and NFCI have the best evidence and free data. The yield curve is a recession indicator with a long, variable lead, and it gave a widely noted false or very delayed signal in 2022–24, so it is poor as a timing trigger. VIX backwardation marks stress but often does not predict further declines. Fear & Greed is a contrarian sentiment composite with no published validation.

### Cited Findings
**HY OAS (FRED BAMLH0A0HYM2)**
- This is the OAS of a cap-weighted index of BB-or-lower US corporate bonds over a spot Treasury curve. It is daily (close), in percent. The latest value was 3.63% on 2026-11-23, with recent values of 3.43–3.76% — [FRED](https://fred.stlouisfed.org/series/BAMLH0A0HYM2)
- **Important data constraint:** from April 2026, FRED keeps only 3 years of observations for this series (history shown is 2023-11-27 onward). The data is "Copyrighted: pre-approval required" and the notes say it is for "internal use only." Redistribution needs ICE written approval — [FRED](https://fred.stlouisfed.org/series/BAMLH0A0HYM2)
- Fed research finds that the predictive power of credit spreads for downturns comes "entirely" from the excess bond premium (EBP), not the default-risk component. A 50 bp rise in EBP raises the 12-month recession probability by about 15 percentage points. The EBP-only model has a pseudo-R² of 0.288, against 0.527 for all indicators. It gave a notable false positive in 2002 — [Fed FEDS Notes 2016](https://www.federalreserve.gov/econresdata/notes/feds-notes/2016/recession-risk-and-the-excess-bond-premium-20160408.html)
- The EBP CSV on that note covers January 1973 to March 2016 and was last updated in April 2016 — [Fed FEDS Notes](https://www.federalreserve.gov/econresdata/notes/feds-notes/2016/recession-risk-and-the-excess-bond-premium-20160408.html). Underlying paper: [Gilchrist & Zakrajšek, NBER w17021](https://www.nber.org/papers/w17021)

**Yield curve**
- FRED T10Y3M (10Y minus 3M constant maturity) is daily, starts 1982-01-04, and is "used to predict recession probabilities." It was 0.55% on 2026-11-24 — [FRED](https://fred.stlouisfed.org/series/T10Y3M)
- The NY Fed model uses the term spread to forecast recession probability 12 months ahead — [NY Fed](https://www.newyorkfed.org/research/capital_markets/ycfaq)
- 10Y-2Y inverted in July 2022 and 10Y-3M in October 2022. Inversion had preceded nearly every recession since the 1950s, wrong only once (mid-1960s), yet no recession followed this time. The conventional lag is 1–2 years. Explanations offered: firms had locked in long-term financing, and the Fed's hiking sequence was unusual — [NBC News](https://www.nbcnews.com/business/economy/indicator-foretold-almost-every-recession-doesnt-seem-working-anymore-rcna163522)
- A Fed note argued that the near-term forward spread is a better recession predictor than 10Y-2Y — [Fed, "Don't Fear the Yield Curve, Reprise" 2022](https://www.federalreserve.gov/econres/notes/feds-notes/dont-fear-the-yield-curve-reprise-20220325.htm) (title and link only; contents not fetched)

**VIX term structure**
- Since 2010 the VIX futures curve has been in backwardation less than 20% of the time. The Cboe author argues backwardation "isn't reliably a warning" of further declines: "Outside of some of the biggest and most memorable market selloffs the results don't pan out," and markets often rebound quickly — [Cboe](https://www.cboe.com/insights/posts/inside-volatility-trading-is-vix-backwardation-necessarily-a-sign-of-a-future-down-market)

**Fear & Greed**
- CNN F&G is the equal-weighted 0–100 average of seven inputs: 52-week highs vs lows, up vs down volume, S&P 500 vs its 125-day MA, the put/call ratio, stocks vs bonds, the junk-vs-IG spread, and VIX. It is designed as a contrarian tool (fear = buy) — [CFI](https://corporatefinanceinstitute.com/resources/capital_markets/fear-and-greed-index/)

**NFCI**
- Chicago Fed NFCI: positive means tighter than average, negative means looser. It is weekly (week ending Friday), with history from 1971-01-08. It covers money markets, debt and equity markets, and traditional and shadow banking. It was -0.478 for the week of 2026-11-13, released Wednesday 2026-11-18, about a 5-day lag — [FRED](https://fred.stlouisfed.org/series/NFCI)

### Inferences
- With the ICE/FRED history cut to 3 years, the app cannot backtest HY OAS over the 2000, 2008 and 2020 cycles using FRED alone. It should store its own history from now on, use NFCI (history since 1971, includes credit) as the long-history proxy, or check the BBB/Moody's alternatives below.
- HY OAS thresholds are usually set relative to the recent past, for example a rise of more than about 1–1.5 pp from the 6–12 month low, or a level above about 5–6% as a stress zone. These are practitioner conventions, not cited, so present them as relative changes rather than fixed levels.
- Yield curve: show it as macro context only. A lead of 12–24 months, plus the 2022–24 miss, makes it unsuitable for drawdown timing.
- VIX: a level above about 30 and VIX/VIX3M > 1 (backwardation) together make a "stress now" light. The Cboe evidence says it is better used to cut new risk than to sell after the fact.

### Gaps
- I did not verify FRED IDs for VIX (believed VIXCLS) and VIX3M (believed VXVCLS), or their licensing (unverified). Cboe also publishes free historical CSVs (unverified).
- I did not verify whether Moody's Baa-10Y (FRED BAA10Y, long history) is still fully available, though it is a likely long-history credit proxy (unverified).
- I found no formal study of CNN F&G predictive power, and CNN has no official API.
- A refreshed EBP series is believed to be on the Fed website, updated monthly (unverified).
- A Korean equivalent (ECOS term spread, credit spread) was not researched.

## 3. Trend/regime filters (S&P 500 vs 200-DMA, 10-month MA): evidence on drawdowns and whipsaw

### Takeaway
This has the strongest evidence for "lose little." Trend filters reliably cut deep drawdowns in prolonged bear markets (1929–32, 2000–02, 2008), and diversified time-series momentum has a century-long record of crisis performance. The costs are whipsaw in V-shaped selloffs, frequent small losses at switch points, and data-mining bias in reported results. Robustness varies by period.

### Cited Findings
- Faber-style monthly stock/bond timing from 1926 (1,037 months): 123 switches (about 1.4 per year), invested in stocks about 66% of months. It beat a 60/40 mix in 78% of rolling 5-year windows. The average drawdown already suffered at the stocks-to-bonds switch was -10.9% (median -8.8%), so the filter does not avoid the first leg down. It is most vulnerable to sharp reversals lasting about 5 months or less and works best in extended trends such as the Depression and recessions — [Mutual Fund Observer](https://www.mutualfundobserver.com/?p=4056)
- The same source cites Zakamulin: reported MA-timing performance contains "substantial data-mining bias" — [Mutual Fund Observer](https://www.mutualfundobserver.com/?p=4056)
- Alpha Architect (Gray) tested simple TAA out of sample. It was not robust in 1927–1977 (a fixed allocation matched its risk-adjusted performance) and showed no strong value-add in 1978–2013. In-sample outperformance was driven largely by long bonds during 2008 — [Alpha Architect](https://alphaarchitect.com/2014/09/are-uber-simple-asset-allocation-systems-robust/)
- Hurst, Ooi & Pedersen tested 67 markets from 1880 to 2016 with a blend of 1-, 3- and 12-month TSMOM at 10% vol. Results were 11.0% gross excess return (7.3% after 2/20 fees), net Sharpe 0.76, positive in every decade, and roughly zero correlation to stocks and bonds. It did well in 8 of the 10 largest 60/40 drawdowns, but had its own drawdowns of up to 25% — [Alpha Architect summary](https://alphaarchitect.com/time-series-momentum-aka-trend-following-the-historical-evidence/); [AQR paper page](https://www.aqr.com/insights/research/journal-article/a-century-of-evidence-on-trend-following-investing)
- Moskowitz, Ooi & Pedersen (2012) found TSMOM profitable on average since 1985 across equity index, bond, commodity and FX futures — [AQR](https://www.aqr.com/insights/research/journal-article/a-century-of-evidence-on-trend-following-investing)
- Original paper: Faber, "A Quantitative Approach to Tactical Asset Allocation" (SSRN 962461) — [Scribd copy](https://www.scribd.com/document/559580322/SSRN-id962461). I could not extract its headline CAGR or max-DD figures.

### Inferences
- For a "lose little" app, S&P 500 vs its 10-month (about 200-day) MA, evaluated monthly or with a buffer band, is the best-supported primary regime light. Expect about 1–2 switches a year, giving up the first ~10% of a decline, and occasional whipsaw (e.g., 2020-style V-shapes).
- Evaluate signals at the month-end close and execute the next trading day, consistent with the repo's no-look-ahead rule.
- Combining trend with a credit or financial-conditions confirmation (HY OAS rising, NFCI above 0) is a common practitioner design. I found no single cited study of that combination.

### Gaps
- I did not obtain the original Faber S&P 500 max-DD and CAGR numbers (commonly quoted as roughly halving max drawdown, unverified).
- No cost or tax-adjusted whipsaw study was fetched.

## 4. Sector/country rotation (relative strength, RRG) and cross-asset context

### Takeaway
Not researched in depth because of the tool budget. Relative strength and RRG are practitioner visualization tools. Cross-sectional momentum has academic support generally, but I fetched no source specific to sector or country rotation and drawdown avoidance.

### Cited Findings
- The CNN F&G "Safe Haven Demand" input (stocks vs bonds relative performance) is one example of a cross-asset risk-appetite gauge — [CFI](https://corporatefinanceinstitute.com/resources/capital_markets/fear-and-greed-index/)
- The Alpha Architect replication shows that a lot of "timing" benefit came from the bond leg (long Treasuries in 2008). So the stock/bond correlation regime matters for where to hide — [Alpha Architect](https://alphaarchitect.com/2014/09/are-uber-simple-asset-allocation-systems-robust/)

### Inferences
- Simple dashboard items: defensive-vs-cyclical ratios (e.g., XLU/XLY, XLP/XLY), SPY/TLT, and US vs world (SPY/ACWX), shown as ratio vs its 200-DMA. These are context, not tested triggers.
- RRG (JdK RS-Ratio/Momentum) is proprietary, so a simple RS = price ratio normalized vs its 52-week mean is a free substitute.

### Gaps
- No evidence was fetched on sector-rotation effectiveness, RRG methodology, or dollar, commodity and real-rate regime studies.
- FRED IDs such as DTWEXBGS (broad dollar), DFII10 (10Y real yield) and DCOILWTICO are believed to exist and be free daily (unverified this session).

## 5. Free availability and publication lag summary

### Takeaway
FRED covers the yield curve (daily, T10Y3M from 1982), NFCI (weekly, about a 5-day lag, from 1971) and HY OAS (daily, but now only 3 years of history and licence-restricted). Breadth and Fear & Greed have no clean free API, and price-derived indicators (trend, breadth, RS) are best computed in-app from daily prices.

### Cited Findings
- BAMLH0A0HYM2: daily, next-day release, 3-year window, internal use only — [FRED](https://fred.stlouisfed.org/series/BAMLH0A0HYM2)
- T10Y3M: daily, same-day evening update, from 1982 — [FRED](https://fred.stlouisfed.org/series/T10Y3M)
- NFCI: weekly, week ends Friday, published the following Wednesday, from 1971 — [FRED](https://fred.stlouisfed.org/series/NFCI)
- EBP (Fed CSV, January 1973 to March 2016 on the 2016 note) — [Fed](https://www.federalreserve.gov/econresdata/notes/feds-notes/2016/recession-risk-and-the-excess-bond-premium-20160408.html)

### Inferences
- Suggested shortlist, in order of evidence × availability:
  1. S&P 500 vs 10-month/200-day MA (primary regime light)
  2. HY OAS change, with a local archive
  3. NFCI
  4. VIX level and VIX/VIX3M
  5. % of constituents above 200-DMA (computed)
  6. 10Y-3M (macro context)
  7. Fear & Greed-style composite (contrarian sentiment only)
- Because the ICE licence says "internal use only," a public repo or app should not redistribute raw HY OAS values. Show derived states, or keep the data private. This needs a licensing check.

### Gaps
- Korean equivalents (ECOS 국고채 10Y-3Y spread, 회사채 AA- spread; KOSPI breadth) were not researched.
- FRED API rate limits and key requirements were not checked (an API key is believed required, unverified).
