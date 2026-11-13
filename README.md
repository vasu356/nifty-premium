# Nifty premium-decay backtest

Backtests short Nifty 50 weekly option strategies (selling premium overnight and
buying it back) on real NSE end-of-day prices from January 2021, after slippage,
brokerage, STT, exchange charges, stamp duty and GST.

Open **`dashboard.html`** in a browser (it works offline; all data is embedded).
**`chain_viewer/`** shows the end-of-day option chain for any day since Jan 2021.

The data is NSE's end-of-day bhavcopy: one row per contract (expiry × strike × CE/PE) per trading day with open, high, low, close, settlement price, contracts traded and open interest. There is no intraday or minute data.

## Pipeline

Run from the project root, in order:

| Step | Script | What it does | Time |
|---|---|---|---|
| 1 | `python3 scripts/01_download.py 2020-01-01 2026-11-12` | Downloads NSE F&O bhavcopies (Nifty rows only) into `data/fo_daily/` and Nifty 50 daily OHLC into `data/index_daily/`. Handles the old CSV format (to Jul 2024) and the UDiFF format (from Jul 2024), and falls back to NSE's market-activity report for 30 Mar 2021, which has no bhavcopy. Days already downloaded are skipped. | ~50 min first run |
| 2 | `python3 scripts/02_build.py` | Merges the daily files into `data/nifty_options_all.csv.gz`, `data/nifty_index.csv` and `data/lot_sizes.csv` (lot size per day, from the published lot or implied by futures turnover). | ~1 min |
| 3 | `python3 scripts/04_run_strategies.py` | Runs all 49 strategies (engine in `scripts/03_backtest.py`) and writes `results/`. | a few min |
| 4 | `python3 scripts/05_make_dashboard.py` | Builds `dashboard.html` from `results/` and `scripts/dashboard_template.html`. | seconds |
| 5 | `python3 scripts/06_build_chain_data.py` | Builds the option-chain viewer's data (`chain_viewer/data/index.json` + one JSON per month, prices in 0.05 ticks). Serve `chain_viewer/` over HTTP to use it locally (`python3 -m http.server -d chain_viewer`). | ~3 min |

To add new trading days, re-run step 1 with a new end date, then steps 2–4.
To test a new idea, add a `Strategy(...)` line to `STRATEGIES` in
`scripts/04_run_strategies.py`, then run steps 3–4. Short write-ups in
`results/findings.json` appear at the top of the dashboard.

## Rules used by the engine

- Entry at the day's close, nearest weekly expiry, OTM strikes that traded at least one contract that day.
- Exit at the next trading day's close; if that day is expiry, the option settles at intrinsic value against the Nifty close.
- Costs per leg: 0.5 pt slippage per order, ₹20 brokerage per order (divided by the lot size of the day), STT 0.0625% / 0.1% (from 1 Oct 2024) on sell premium, 0.125% on exercised long options, exchange charges 0.05% / 0.0353%, SEBI fee, stamp duty 0.003% on buys, 18% GST.
- Stops are checked against the next day's high; if the day opened beyond the stop, the fill is the open price.
- P&L is in points per unit; ₹ per lot in the dashboard uses the current lot of 65.

## Files

- `results/strategy_summary.csv` — one row per strategy (net, gross, costs, win rate, drawdown, per-year net)
- `results/all_trades.csv.gz` — every trade of every strategy
- `results/user_by_dte.csv`, `results/user_by_move.csv` — breakdowns of the ₹30 daily strategy
- `results/robustness_grid.csv`, `results/cost_sensitivity.csv`, `results/move_distribution.csv`
- `data/fo_daily/`, `data/index_daily/` — raw daily downloads (Nifty rows only, ~60 MB). Steps 2–4 need only the merged files in `data/`.

## Nifty market data and pattern study (added later)

- `scripts/14_download_nifty.py` downloads Nifty 50 and India VIX history from Yahoo Finance into `data/market/`
  (daily since 2007, hourly ~2 years, 5-min/15-min ~2 months, 1-min ~18 days). Yahoo only serves a rolling window of
  intraday data, so re-run it regularly to build a longer minute-level archive. Open and close match NSE's index file exactly.
- `scripts/15_patterns_options.py` implied-vs-realised moves, strike breach rates, hourly risk profile.
- `scripts/16_pattern_strategies.py` tests of open-price exits, VIX filters/scaling and conditional performance.
- `scripts/08_strategy_lab.py`, `09_run_lab.py`, `10_search.py`, `11_walkforward.py`, `12_dte3.py`, `13_formula_lab.py`
  are the strategy lab and the search scripts. Results are in `results/manual/`.
