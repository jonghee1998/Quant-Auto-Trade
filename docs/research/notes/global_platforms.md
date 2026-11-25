# Global investing/quant platforms: dashboard and screen inventory

Scope: what result screens, panels and metric names leading platforms show, as input for a personal quant app (US ETFs and stocks, monthly mid/long-term plus swing strategies, lab → paper → live, benchmark = holding an S&P 500 ETF, goal "lose little, win big"). Sources are mostly official docs, fetched 2026-11. A few pages (Finviz homepage, StockCharts Market Summary, Composer invest dashboard) did not describe their full layouts; those points are under Gaps.

## Q1. Portfolio Visualizer: result screens and metrics

### Takeaway
Portfolio Visualizer's Backtest Portfolio output is a long, single-page report: a "Highlights" strip, a growth chart, then about 25 tables and charts. It covers absolute performance (CAGR, stdev, best/worst year, MDD, Sharpe, Sortino), comparison with the benchmark (active return, tracking error, IR, up/down capture), drawdown episodes, rolling returns, and return/risk decomposition by asset. It is the most complete public template for a "monthly allocation strategy vs SPY" report.

### Cited Findings
- Result sections, in page order: Highlights (Return: Annualized Return, Portfolio Return, Benchmark Relative; Risk: Standard Deviation, Drawdown); Portfolio Growth chart (log scale and inflation-adjusted options); Performance Summary; Annual Returns (chart + table); Trailing Returns; Holdings Based Style Analysis (Asset Allocation, Equity Market Cap, Equity Sectors, FI Credit Quality, FI Maturity charts); Annualized Active Return; Active Return Contribution; Rolling Active Return; Up vs. Down Market Performance; Risk and Return Metrics; Monthly Returns; Drawdowns chart; Historical Market Stress Periods; Drawdowns tables (separately for the portfolio and for the SPY benchmark); Portfolio Assets; Portfolio Asset Performance; Monthly Correlations; Portfolio Return Decomposition; Portfolio Risk Decomposition; Annual Asset Returns; Rolling Returns table; Annualized Rolling Return 3Y and 5Y charts — [Portfolio Visualizer Backtest Portfolio](https://www.portfoliovisualizer.com/backtest-portfolio)
- Performance Summary metrics: Start Balance, End Balance, Annualized Return (CAGR), Standard Deviation, Best Year, Worst Year, Maximum Drawdown, Sharpe Ratio, Sortino Ratio, Active Return, Tracking Error, Information Ratio, Benchmark Correlation — [PV](https://www.portfoliovisualizer.com/backtest-portfolio)
- Risk and Return Metrics table: Arithmetic Mean (monthly and annualized), Geometric Mean (monthly and annualized), Standard Deviation (monthly and annualized), Downside Deviation (monthly), Maximum Drawdown, Benchmark Correlation, Beta, Alpha (annualized), R², Sharpe, Sortino, Treynor (%), Calmar, Modigliani–Modigliani Measure, Active Return, Tracking Error, Information Ratio, Skewness, Excess Kurtosis, Historical VaR (5%), Analytical VaR (5%), Conditional VaR (5%), Upside Capture Ratio (%), Downside Capture Ratio (%), Safe Withdrawal Rate, Perpetual Withdrawal Rate, Positive Periods, Gain/Loss Ratio — [PV](https://www.portfoliovisualizer.com/backtest-portfolio)
- Drawdown tables use these columns: Rank, Start, End, Length, Recovery By, Recovery Time, Underwater Period, Drawdown — [PV](https://www.portfoliovisualizer.com/backtest-portfolio)
- Trailing Returns: 3M, YTD, 1Y, 3Y, 5Y, 10Y, Full, plus annualized 3Y/5Y return and stdev. Rolling Returns table: Average, High and Low for 1, 3, 5, 7 and 10-year windows — [PV](https://www.portfoliovisualizer.com/backtest-portfolio)
- Up vs. Down Market Performance: Occurrences (Above Benchmark, Below Benchmark, Total, % Above Benchmark) and Average Active Return in each case — [PV](https://www.portfoliovisualizer.com/backtest-portfolio)
- Portfolio Assets (per-asset rows): CAGR, Stdev, Best Year, Worst Year, Max Drawdown, Sharpe, Sortino. Annual and Monthly Returns tables list return and balance for the portfolio, the benchmark and each asset, with inflation shown on the annual table — [PV](https://www.portfoliovisualizer.com/backtest-portfolio)
- Tactical Asset Allocation model types: Shiller PE10 valuation, Seasonal, Moving averages (single asset or portfolio assets), Momentum (relative strength), Dual momentum, Adaptive allocation (RS plus risk parity or min variance), Target volatility, Risk managed allocation. Options include "Show Regime Performance" (default regime is Market Volatility), Benchmark (S&P 500 TR, US Bond Aggregate or a custom ticker) and Compared Allocation — [PV Tactical Asset Allocation](https://www.portfoliovisualizer.com/tactical-asset-allocation-model)
- Factor Regression inputs: CAPM, 3-, 4- and 5-factor models (MKT, SMB, HML, MOM, RMW, CMA) and the q-factor model, with optional STREV, LTREV, QMJ and BAB; fixed-income TRM and CDT factors; OLS or LASSO; daily or monthly returns; roll period of 12–60 months; robust regression option — [PV Factor Analysis](https://www.portfoliovisualizer.com/factor-analysis)

### Inferences
- For a "lose little, win big" goal, the most relevant PV blocks are Downside Capture vs Upside Capture, Max Drawdown plus the drawdown-episode table (recovery time), Worst Year, and Up vs Down Market performance against SPY.
- The "Historical Market Stress Periods" table and QuantConnect's "Crisis Events" (Q2) are the same idea: show performance during named crash windows.

### Gaps
- I could not see the result screens for Tactical Allocation (for example, holdings by period or the current signal) or the factor regression output columns (t-stat, p-value), because the pages only describe inputs.

## Q2. QuantConnect and Composer: backtest, paper and live presentation

### Takeaway
QuantConnect has the most complete engineering-style results page: a runtime-statistics banner, built-in charts (equity, drawdown, benchmark, exposure, turnover, capacity), tabs for Overview, Orders, Trades, Insights, Logs and Code, and a downloadable report with crisis events and rolling beta/Sharpe. The live page reuses the same layout and adds a Holdings tab. Composer is retail-simple: the default benchmark is SPY, it shows a small metric set (cumulative/annualized return, Sharpe, stdev, MDD, Calmar, alpha/beta/R²), and backtests include explicit fee and slippage toggles and a historical-allocations view.

### Cited Findings
**QuantConnect backtest results page**
- Runtime Statistics banner: Equity, Fees, Holdings, Net Profit, PSR, Return, Unrealized, Volume — [QC Backtest Results](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results)
- Built-in charts: Strategy Equity (equity plus periodic returns), Capacity, Drawdown, Benchmark, Exposure (long/short ratios), Assets Sales Volume, Portfolio Turnover, Portfolio Margin, Performance (system resources, off by default), Asset Plot (paid tiers) — [QC](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results)
- Overview tab, Overall Statistics: PSR, Total Trades, Average Win, Average Loss, Drawdown, Net Profit, Win Rate, Loss Rate, Profit-Loss Ratio, Expectancy, Compounding Annual Return, Sharpe, Alpha, Beta, Annual Variance, Annual Standard Deviation, Information Ratio, Tracking Error, Treynor Ratio, Total Fees, Estimated Strategy Capacity, Lowest Capacity Asset. Some of these also appear in a Rolling Statistics table — [QC](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results)
- Tabs: Overview, Report, Orders (order events: submitted, filled, partial, updated, canceled; CSV export), Trades (fills per trade; CSV), Insights (JSON), Logs (filterable), Code (the project files used in that backtest, which gives a de facto version snapshot), Share Results — [QC](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results)
- Backtest Report sections: Key Statistics (Runtime Days, Turnover, CAGR, Markets, Trades per day, Drawdown, Probabilistic SR, Sharpe, Information Ratio, Strategy Capacity); Returns (Returns per Trade histogram, Daily Returns, Monthly Returns heat map, Annual Returns, Cumulative Returns vs benchmark); Asset Allocation pie; Drawdown underwater plot with the top 5 periods; Rolling Portfolio Beta (6 and 12 months); Rolling Sharpe (6 and 12 months); Exposure (Leverage, Long-Short Exposure by Asset Class); Crisis Events (DotCom 2000, GFC 2007, Flash Crash 2010, COVID-19 2020, Russia–Ukraine 2022-23, AI Boom 2022–present, and others; only events inside the backtest window are shown); Parameters — [QC Backtest Report](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/report)
- The live results page uses the same Runtime Statistics banner and built-in charts (Strategy Equity, Drawdown, Benchmark, Exposure, Turnover, Margin and others) plus custom charts. It adds a Holdings tab (positions and cash), Orders, Trades (closed), Insights, Logs, Code (with Clone Algorithm), Errors (runtime errors and automatic restarts) and Share (including Live Stream). Stop and liquidate controls are documented separately under "Algorithm Control" — [QC Live Results](https://www.quantconnect.com/docs/v2/cloud-platform/live-trading/results)

**Composer (composer.trade)**
- Backtest components: time period (1 year by default), initial investment, fees/costs/slippage, chart view, comparison benchmarks, final values and costs, Alpha, Beta, R², R, Cumulative Return, Annualized Return, Trailing 1-Month and 3-Month Return, Sharpe, StDev, Max Drawdown, Calmar, Historical Allocations — [Composer: How do Backtests Work](https://help.composer.trade/article/215-7-how-do-backtests-work-in-composer)
- The default benchmark is SPY. Users can add other symphonies, watchlist or live-portfolio items, or any stock or ETF. Benchmark metrics are limited by the shortest data history — [Composer](https://help.composer.trade/article/215-7-how-do-backtests-work-in-composer)
- Costs: regulatory fees (SEC/FINRA) plus the Trading Pass subscription. Default slippage is 1 bp, adjustable and toggleable. Dividends are assumed reinvested in both backtests and live trading. Live decisions use real-time quotes during the trading window — [Composer Backtest Basics](https://help.composer.trade/article/67-backtest-basics); [Composer](https://help.composer.trade/article/215-7-how-do-backtests-work-in-composer)
- After investing, a symphony trades automatically at a chosen frequency and shows monitoring metrics. The help page gives no further detail — [Composer: Investing in a Symphony](https://help.composer.trade/article/92-tutorial-investing-in-a-symphony)

**TradingView Strategy Tester (Overview tab), for comparison**
- Charts: Performance (cumulative PnL per closed trade, optional Buy & Hold line, margin-call layer, currency or % view); Profit structure bars; Benchmarking (max/current/min of strategy vs Buy & Hold); ROI distribution histogram; Trades distribution donut (winners, losers, breakevens); Run-ups and drawdowns; Margin usage — [TradingView Overview tab](https://www.tradingview.com/support/solutions/43000681733-overview-tab/)
- Metrics: Net PnL, Gross profit/loss, Profit factor, Commission, Expectancy; Buy & hold PnL / % gain and Strategy outperformance; Sharpe, Sortino; trade counts, % profitable, average/largest win and loss, avg bars in trade; Max drawdown (close-to-close, intrabar, % of capital), Return of max DD, average DD duration; CAGR, Account size required, margin stats — [TradingView](https://www.tradingview.com/support/solutions/43000681733-overview-tab/)

### Inferences
- A common pattern across QC, Composer and TradingView is a KPI header, then an equity curve against the benchmark (SPY or buy-and-hold), then a drawdown chart, then a statistics table, then trade/order logs. QC's live page is deliberately the same layout as its backtest page, which supports a "lab → paper → live, same screen" design.
- Turnover, fees and slippage are shown as first-class items (QC Portfolio Turnover chart and Total Fees; Composer cost toggles). For a monthly-rebalance strategy, showing cost drag explicitly is cheap and important.
- Versioning: QC ties each backtest to its code snapshot through the Code tab. I found no documented formal "strategy version history" UI in Composer.

### Gaps
- I did not verify Composer's paper-trading mode or its version/edit history. The help pages fetched do not describe them.
- I did not find a QC doc page for a paper-vs-live comparison screen. Paper trading in QC is a brokerage choice under live deployment (from general knowledge, not verified here).

## Q3. Koyfin, Finviz, StockCharts, TradingView: market overview, heatmap, rotation, breadth

### Takeaway
Market-overview "homes" are built from a few elements: index and asset tiles with mini-charts, tables of percent change over a selectable timeframe, a sector/industry heatmap (sized by market cap, colored by % change), and sector-rotation views (RRG). Koyfin offers pre-built thematic dashboards plus drag-and-drop widgets. Finviz centers on heatmaps, signals and gainers. StockCharts offers a Market Summary by asset class plus RRG.

### Cited Findings
- **Koyfin pre-built market dashboards**: Today's Markets (world equity, credit, FX, commodities), World Equity Indices, US Sectors, Countries, Factors, Global Yields, Global Yield Curves, Recent IPOs, Currencies, World Economics, Commodities, Corporate Credit, Fixed Income Factors. The Economic Calendar is a separate tool — [Koyfin Market Dashboards](https://www.koyfin.com/features/macro-dashboards)
- **Koyfin My Dashboards** widgets: Table/Watchlist, Historical Graph, Performance Graph (cumulative % change since the start date), and news. Widgets can be resized and dragged. A template or blank start is available. 7 color "groups" link widgets, so dragging a ticker from a table into a graph changes the security — [Koyfin MYD help](https://www.koyfin.com/help/mydashboards-myd)
- **Finviz homepage (Elite)**: configurable Maps (two at once; map type, performance metric and session can be set), signals with minimum price and average volume filters, pre-market, regular and after-hours views, gainers list, auto-refresh, and an auto mode that switches to after-hours data after the close — [Finviz blog](https://finviz.com/blog/new-finviz-homepage-features-for-elite-members/)
- **Finviz Matrix**: a grid with industries as rows and market-cap tiers as columns, or a cluster view. Color metric options include 1-day (default) to multi-year performance, drawdown from 52W high, gain from 52W low, relative volume, valuation (P/E, fwd P/E, PEG, P/S, EV/EBITDA), growth, profitability, short float, insider activity and analyst recs. Hover shows "Why Is It Moving" — [Finviz Matrix](https://finviz.com/blog/the-finviz-matrix-market-breadth-visualized/)
- **TradingView heatmaps**: Stock, ETF and Crypto. Stocks are sized by market cap, volume, turnover or mono and colored by change, performance, pre/post-market change, relative volume, volatility or gap. ETFs are sized by AUM, volume or turnover, colored by change, performance, NAV total return, top weight, volatility or beta, and grouped by asset class. Stocks are grouped by sector. Clicking a group zooms in, clicking a tile opens the symbol page, and hovering shows a tooltip — [TradingView Heatmaps](https://www.tradingview.com/support/solutions/43000766446)
- **StockCharts Market Summary**: sections for Equities, Intermarket, Bonds, Commodities and Currencies. Mini-charts at the top use a Timeframe dropdown, and tables show Change and % Change for that timeframe — [StockCharts Market Summary help](https://help.stockcharts.com/charts-and-tools/research-tools/market-summary)
- **RRG (StockCharts)**: x-axis = JdK RS-Ratio (trend of relative strength), y-axis = JdK RS-Momentum. Both are normalized to 100, and the benchmark sits at the 100/100 crosshair. The quadrants are Leading (green), Weakening (yellow), Lagging (red) and Improving (blue), with idealized clockwise rotation. Tails show recent path and their length is adjustable. A ranking table orders symbols by quadrant and distance from the benchmark. The typical example is the nine sector SPDRs against the S&P 500. The page notes that RRG is not a trading system — [StockCharts ChartSchool RRG](https://chartschool.stockcharts.com/table-of-contents/chart-analysis/chart-types/relative-rotation-graphs-rrg-charts.md)

### Inferences
- For US ETF rotation, an RRG of sector/factor ETFs against SPY plus a sector heatmap colored by 1M/3M/6M performance is the closest match to "where is momentum."
- Koyfin's pattern of linked widgets with a watchlist driving the charts is a good model for a "watchlist → detail" interaction.

### Gaps
- The Finviz homepage breadth bars (Advancing/Declining, New High/New Low, above SMA50/SMA200) are widely seen on the live site, but the fetched source did not describe them. I did not verify them from docs.
- StockCharts' members "Your Dashboard" panels and Sector Summary columns were not fetched in detail (pages exist: [members dashboard](https://help.stockcharts.com/finding-your-way-around/members-dashboard), [Sector Summary](https://help.stockcharts.com/charts-and-tools/research-tools/sector-summary)).
- I did not research TradingView screener and watchlist column defaults.

## Q4. Institutional: Bloomberg PORT risk and performance blocks

### Takeaway
Bloomberg PORT is organized as tabs that match a PM's daily questions: how am I doing today (Intraday), over the period (Performance), why (Attribution), what do I own (Characteristics), how much active risk (Tracking Error), how much I could lose (VaR), what if (Scenarios), and what to trade (Trade Simulation / Optimization).

### Cited Findings
- Intraday tab: real-time tables, charts and heat maps of performance, absolute or against a benchmark, sliced by sector, geography or market cap — [Bloomberg PORT brochure](https://ftl.hsu.edu.hk/wp-content/uploads/2019/10/port_portfolio_and_risk_analytics-brochure.pdf)
- Performance tab: performance over 1D, 1M, YTD and other periods; best risk/return sectors or holdings vs the benchmark; standard deviation, beta, realized tracking error — [PORT brochure](https://ftl.hsu.edu.hk/wp-content/uploads/2019/10/port_portfolio_and_risk_analytics-brochure.pdf)
- Attribution tab: allocation effect, security selection effect, currency effect, curve effect (FI), with drill-down into capital events and dividends — [PORT brochure](https://ftl.hsu.edu.hk/wp-content/uploads/2019/10/port_portfolio_and_risk_analytics-brochure.pdf)
- Characteristics tab: aggregated P/E, dividend yield and duration by sector, country or custom grouping; top/bottom 10 holdings by weight, P/E or duration; relative exposure charts vs the benchmark — [PORT brochure](https://ftl.hsu.edu.hk/wp-content/uploads/2019/10/port_portfolio_and_risk_analytics-brochure.pdf)
- Tracking Error tab: ex-ante multi-factor risk showing the amount and sources of risk, plus factor P&L attribution — [PORT brochure](https://ftl.hsu.edu.hk/wp-content/uploads/2019/10/port_portfolio_and_risk_analytics-brochure.pdf)
- VaR tab: absolute and relative VaR (Monte Carlo, Historical, Parametric) at multiple confidence levels. Scenarios tab: historical stress (for example 2008) and custom scenarios with factor sensitivities. Trade Simulation shows the what-if impact of trades. The Optimizer covers goals and constraints, TCA and rebalancing — [PORT brochure](https://ftl.hsu.edu.hk/wp-content/uploads/2019/10/port_portfolio_and_risk_analytics-brochure.pdf)

### Inferences
- A scaled-down personal version could be: Today (P&L vs SPY), Period performance (vs SPY), Attribution (which holding or sleeve contributed), Exposures (sector/asset-class weights vs SPY), Risk (realized vol, beta, tracking error, historical VaR/CVaR), and Stress (crisis-window replay). Factor-model ex-ante TE and an optimizer are niche for a single-user app.

### Gaps
- The brochure is circa 2019. I did not verify the 2025–26 PORT Enterprise layout, which a press release mentions adding AI portfolio commentary ([Bloomberg press](https://www.bloomberg.com/company/press/bloomberg-advances-portfolio-analytics-with-launch-of-ai-portfolio-commentary-in-port-enterprise), not fetched).

## Q5. Common must-haves vs niche elements

### Takeaway
Across all the platforms reviewed, the near-universal core is: an equity curve against the benchmark (SPY or buy-and-hold), a drawdown/underwater chart, a CAGR/return + volatility + Max Drawdown + Sharpe KPI set, period returns (annual/monthly), and a trade/order log or allocation history. Sortino, Calmar, alpha/beta, tracking error/IR, rolling stats and crisis-period tables are common in quant tools. VaR, factor attribution, capacity and optimizers are niche or institutional.

### Cited Findings (cross-platform matrix, built from the sources above)
| Element | PV | QuantConnect | Composer | TradingView ST | Bloomberg PORT |
|---|---|---|---|---|---|
| Equity curve vs benchmark | Portfolio Growth vs SPY | Strategy Equity + Benchmark; Cumulative Returns vs benchmark | Chart vs SPY (default) | Performance + Buy & Hold line | Performance vs benchmark |
| Drawdown chart/table | Drawdowns chart + episode table | Drawdown chart; underwater top-5 | Max Drawdown (metric) | Run-ups & drawdowns | (VaR/Scenarios instead) |
| CAGR / annualized return | yes | Compounding Annual Return / CAGR | Annualized Return | CAGR | period perf |
| Volatility (stdev) | yes | Annual Std Dev | StDev | — | Std dev |
| Sharpe | yes | yes (+PSR) | yes | yes | — (not named) |
| Sortino | yes | — | — | yes | — |
| Calmar | yes | — | yes | — | — |
| Alpha/Beta/R² | yes | Alpha, Beta | Alpha, Beta, R², R | — | Beta |
| Tracking error / IR | yes | yes | — | — | Tracking Error tab |
| Up/down capture | yes | — | — | — | — |
| Annual/monthly returns | tables + charts | Monthly heat map, annual bars | trailing 1M/3M | — | — |
| Rolling stats | Rolling 1–10Y returns, rolling active return | Rolling Beta & Sharpe 6/12M | — | — | — |
| Crisis/stress periods | Historical Market Stress Periods | Crisis Events | — | — | Scenarios |
| VaR/CVaR | Hist/Analytical VaR, CVaR 5% | — | — | — | VaR tab |
| Fees/slippage/turnover | expense ratios | Total Fees, Portfolio Turnover chart | fees + 1bp slippage toggles | Commission | TCA (optimizer) |
| Trade log / orders | — | Orders, Trades tabs | Historical Allocations | trade list | Trade Simulation |
| Allocation/holdings view | Holdings style analysis, assets table | Asset Allocation pie; Holdings (live) | Historical Allocations | — | Characteristics |
| Attribution / decomposition | Return & Risk Decomposition, Active Return Contribution | — | — | — | Attribution tab |

Sources: [PV](https://www.portfoliovisualizer.com/backtest-portfolio), [QC Results](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/results), [QC Report](https://www.quantconnect.com/docs/v2/cloud-platform/backtesting/report), [Composer](https://help.composer.trade/article/215-7-how-do-backtests-work-in-composer), [TradingView](https://www.tradingview.com/support/solutions/43000681733-overview-tab/), [PORT](https://ftl.hsu.edu.hk/wp-content/uploads/2019/10/port_portfolio_and_risk_analytics-brochure.pdf). A "—" means the element was not found in the fetched docs, not that it is confirmed absent.

Market-overview must-haves (Q3 sources): index/asset tiles with % change and a timeframe selector; a sector heatmap (size = market cap or AUM, color = % change); a watchlist table linked to a chart. Niche: RRG (StockCharts, a few others), Finviz Matrix, factor dashboards (Koyfin).

### Inferences
- Must-have for the user's app: KPI strip (CAGR, MDD, Sharpe, vol, current DD, excess vs SPY), equity curve vs SPY (log option), underwater chart with an episode table (depth, length, recovery), annual-return bars vs SPY plus a monthly heatmap, a trade/rebalance log, a holdings/allocation view, and a cost line (fees, slippage, turnover). Use the same layout for backtest, paper and live, as QC does.
- Specific to "lose little, win big": Up/Down Capture, Sortino, Calmar, Worst Year/Month, Gain/Loss ratio, a crisis-window table (PV or QC style), and rolling 12M excess return vs SPY.
- Nice-to-have: RRG of sector ETFs vs SPY, a sector heatmap, PSR (overfitting check in the lab), rolling beta/Sharpe.
- Niche/skip for v1: ex-ante factor TE, an optimizer, capacity estimates, intraday heatmaps.

### Gaps
- Several "—" cells may be false negatives because some docs were only partially available.
