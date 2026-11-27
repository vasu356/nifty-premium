# Handoff: Nifty weekly option-selling research (state as of 27 Nov 2026)

Paste everything below into a new chat to continue.

---

## Who I am and what we're doing

I trade Nifty 50 weekly options (selling premium for decay) on HDFC Sky, with lot size **65**.
Over many sessions we researched and backtested premium-selling strategies end to end on real NSE data.
Continue from here: use the repo, don't rebuild from scratch, and show tables and month-wise results in chat.
Test properly (no rushing, honest about overfitting), and give answers in simple, short steps.

## Repository (everything is here)

- GitHub: **https://github.com/vasu356/nifty-premium**, branch `main`.
  It's public, and needs to stay public for Claude to push. Clone it: `git clone https://github.com/vasu356/nifty-premium`.
- `README.md` describes every script.
- `docs/TRADING_CHECKLIST.md` holds the current trading rules, with worked examples and timing.
- `docs/HANDOFF_PROMPT.md` is this file.

### Data in the repo

- **`data/nifty_options_all.csv.gz`:** NSE F&O bhavcopy, Nifty options only. 2,606,525 rows, **1 Jan 2021 to 23 Nov 2026**, 1,461 days, 339 expiries.
  - Columns: date, expiry, strike, opt, open, high, low, close, settle, contracts, oi.
  - **close** = NSE official closing price, the 30-minute VWAP: 3:00 to 3:30 PM before 3 Aug 2026, then 3:10 to 3:40 PM. This is not the last trade.
  - **open** = the first trade of the day.
- **`data/nifty_index.csv`:** Nifty 50 daily OHLC, 2020 to 23 Nov 2026. Since 3 Aug 2026 the close is the closing-auction price.
- **`data/fo_daily/`, `data/index_daily/`:** raw daily downloads. `scripts/01_download.py START END` fetches new days and `scripts/02_build.py` rebuilds.
- **`data/market_user/`:** my uploaded Nifty 50 index OHLC at 1/3/5/10/15/30 min, 1 hour, day, week, month and year, from 2021 to 13 Nov 2026.
- **`data/market/`:** Yahoo data (`scripts/14_download_nifty.py`): daily Nifty since 2007, India VIX since 2008, and recent intraday bars.
  - **`data/market/nifty_1min_combined.csv`** = my 1-min file + Yahoo 1-min for 16 to 23 Nov 2026. Yahoo matches my file within about 1 point on overlapping days.
- **`data/lot_sizes.csv`:** lot size history 75 → 50 → 25 → 75 → 65 (65 from 31 Dec 2025).
- **`results/manual/`:** all result CSVs. **`results/charts/`** holds the equity charts (`final_plans_equity.png`, `midweek_put_equity.png`).

### Key scripts (in order of the research)

| Scripts | What they do |
|---|---|
| `08_strategy_lab.py` | Core engine (`Lab` class: chain lookup, `by_strike`, `by_price`, `atm`, `dte`) |
| `13_formula_lab.py` | Formula strike-selection lab |
| `17` to `24` | Extra-day (Tue/Wed/Thu) signals, walk-forward ML, range/pattern forecasting |
| `25` to `28` | Sep 2025+ deep study: strike grids, holding periods, wings, one-sided, weekly plans |
| `29` to `31` | Option **buying** tests |
| `32` to `34` | Decay map, which found the far-OTM put |
| `35` to `37` | Which Nifty reading to use for strikes (closing-auction era), multiplier grid with live 3:14 reading |
| `38` to `40` | **Final realistic grid** (live 3:14 PM Nifty) and month-wise plan comparison from Sep 2025 |

Python setup: pandas, numpy, scipy, statsmodels, scikit-learn and matplotlib (`pip install` if missing). Run scripts with `python3 -I`.

## Market facts that matter

- **Expiry:** weekly Nifty expiry is **Tuesday** since 2 Sep 2025 (Thursday before). On a holiday it moves to the previous trading day, e.g. Tue 24 Nov 2026 was a holiday, so expiry was Mon 23 Nov.
- **Count days to expiry in trading days.** Holidays then shift every trade day automatically.
- **Closing auction session (CAS) from 3 Aug 2026:**
  - Live Nifty index stops at **3:14 PM**.
  - The auction runs 3:15 to about 3:35. The official close is the auction price, printed at about 3:28 to 3:29 in minute data.
  - F&O trades until 3:40. Expiry settlement uses the auction close.
- **From 7 Dec 2026** (from news and broker reports; NSE circular not verified):
  - Cash trading runs to 3:30 and the CAS runs 3:30 to 3:40.
  - F&O runs to 3:45; on expiry day, expiring contracts stop at 3:30.
  - Expiry settlement goes back to a **30-minute VWAP** of normal trading.
- **Which Nifty to read for strikes:**
  - Read the **live index at the last live minute: 3:14 PM now, 3:29 PM from 7 Dec**. On 7 Dec, check whether Nifty still freezes at 3:15.
  - Don't use the official close (known too late) or the options-implied Nifty, which tested worst in every era.
- **Charges assumption:** ₹130 per 2-leg trade = **1 point per leg** at 65 units.

## The current strategy (final, realistic version)

**Inputs, read at 3:14 PM (3:29 from 7 Dec):**
- **Nifty** = the live Nifty 50 index value.
- **S** = the ATM call price + the ATM put price, for the nearest expiry (ATM = strike nearest to Nifty).
- **Centre** = Nifty + 0.15 × (Nifty − official close 5 trading days ago).

Round all strikes to the nearest 50; if exactly halfway, take the strike further from Nifty.

| Trading days to expiry | Usual day | Trade | Strikes | Exit |
|---|---|---|---|---|
| 2 | Fri | Short strangle | call = centre + **0.75**×S, put = centre − **1.0**×S | Buy back at next day's close (Mon), even at a loss |
| 1 | Mon | Short strangle | call = centre + **0.5**×S, put = centre − **1.0**×S | Hold into expiry. Until 4 Dec, buy back any leg near or in the money before 3:15 PM on expiry day; from 7 Dec, before 3:30 PM |
| 4 | Wed | Short put only | put = Nifty − **2.5**×S | Hold to expiry, no stop |
| 3 | Thu | Short put only | put = Nifty − **2.5**×S | Hold to expiry, no stop |
| 5 | Tue (old expiry day) | Short put only (optional, later) | put = Nifty − 2.5×S | Hold to expiry |

- **Sell timing:** 3:15 to 3:35 PM now, 3:30 to 3:40 PM from 7 Dec.
- **Orders and size:** limit orders near the middle of the bid and ask, 1 lot each.

### Realistic results

Strikes from live 3:14 PM Nifty, NSE closing prices, charges included, 1 lot per position, **1 Sep 2025 to 23 Nov 2026** (`scripts/40_final_plans.py`):

| Plan | Net points | ₹ | Worst week | Months positive | Since 3 Aug 2026 | 2021 to Aug 2025 |
|---|---|---|---|---|---|---|
| A original (Fri + Mon both 0.75/1.0) | +2,135 | ₹1.39L | −426 | 12/15 | −13 | +5,148 |
| B Fri 0.75 + Mon call 0.5 | +2,330 | ₹1.51L | −459 | 12/15 | +64 | +5,549 |
| **C = B + far puts Wed, Thu (recommended start)** | **+3,287** | **₹2.14L** | −433 | 12/15 | +109 | +8,228 |
| D = C + far put Tue | +3,763 | ₹2.45L | −419 | 12/15 | +215 | +9,559 |

**Plan C by month (points):**

| Month | Net |
|---|---|
| Sep 2025 | +352 |
| Oct 2025 | +207 |
| Nov 2025 | +329 |
| Dec 2025 | +90 |
| Jan 2026 | +116 |
| Feb 2026 | **−133** |
| Mar 2026 | +440 |
| Apr 2026 | +728 |
| May 2026 | +306 |
| Jun 2026 | +338 |
| Jul 2026 | +403 |
| Aug 2026 | +453 |
| Sep 2026 | +190 |
| Oct 2026 | **−355** |
| Nov 2026 (to 23rd) | **−179** |
| **Total** | **+3,287** |

**By component:** Fri +865, Mon +1,465, put Wed +480, put Thu +477, put Tue +476.

**Weak spot:** Monday trades since 3 Aug 2026 average −4.3 per trade (17 trades), against +32 before. The median is still +57; a few big expiry-day moves caused it (2 Nov −248, 20 Nov −199, 13 Oct −289). Too few trades to change the rule yet. Re-test after the 7 Dec settlement change.

**Far put facts:**
- **Distance:** about 2.6 to 3.1% below Nifty (median about 630 to 780 points), premium about ₹6 to ₹12. About 97% expire worthless.
- **Track record:** positive in every year 2021 to 2026, for every entry day.
- **Risk:** mid-week value can briefly jump 25 to 45× (₹9 to ₹409 in Apr 2025). The worst final result was −331. The worst combined week (formula + puts) was −694 points (26 Sep to 3 Oct 2024).
- **Tail risk:** there's no 2020-style crash in the data.

## Tested and rejected (don't redo unless asked)

- **Strike choice:**
  - Fixed-premium strikes (nearest ₹10 to ₹100, including ₹30): all much worse than the straddle formula (₹30 made +1,211 against +2,757 on the same trades).
  - Strikes from a forecast range (volatility/VIX models): same as the straddle formula, no gain.
- **Exits and protection:**
  - Wings (iron condors): worse. Stops and take-profits: worse.
  - Holding Friday's position into Tuesday: worse tail (−5 became −370 in some weeks).
  - Exiting at next open: not reliable (open price = first trade).
- **Which days and expiries to trade:**
  - Next-week expiries, overnight: weak.
  - Extra overnight trades on Tue/Wed/Thu (formula or ₹30): lose money. Trend filters and walk-forward ML (Ridge/GBM) found no reliable edge.
  - Thursday → Tuesday hold: positive in Sep 2025 to Nov 2026, but its old-era equivalent was inconsistent. Kept only as an idea.
  - 2 lots on Friday: looked good in Sep 2025 to Nov 2026 (Friday's worst trade −90), but it's unproven in older data. Optional.
- **Direction and forecasting:**
  - Selling only the call: a direction bet (flat in 2021 and 2025).
  - Next-day direction prediction: AUC 0.51 to 0.56, flips sign by year. Candle and weekly patterns add nothing beyond volatility + VIX.
- **Sizing and filters:**
  - Sizing by richness ratio: real but modest. Half size on high VIX: neutral.
- **Option buying:**
  - Buying on Tuesday (expiry day) and selling Wednesday: about break-even; needs a 150+ point move; call/put results flip between eras. Rejected.
  - Buying an ATM straddle overnight on any weekday: loses on almost every day.

## Infrastructure status and next steps

- **Live data:** Yahoo gives live Nifty (`query1.finance.yahoo.com/v8/finance/chart/^NSEI`). NSE's website blocks automated access, so **don't try to bypass it**.
- **Live option prices need my Angel One SmartAPI account.** I use it for data only; I trade on HDFC Sky.
  - Login needs: **API key, client ID, PIN, TOTP secret**. The login body needs client ID + PIN + a fresh TOTP, so network secrets (header-only) can't do it.
  - Plan: create a separate personal cloud environment **`nifty-premium`** (not "Default"). I add env vars there myself: `ANGEL_API_KEY`, `ANGEL_CLIENT_ID`, `ANGEL_PIN`, `ANGEL_TOTP_SECRET`. Never paste them in chat.
  - Scripts must read them only from the environment and never print, log or commit them.
- **To build next, once the environment exists:**
  1. A live script: log in to Angel One, fetch Nifty LTP + ATM call/put LTP for the nearest expiry, apply the formula, and output exact strikes.
  2. Scheduled tasks on trading days (IST):
     - **2:55 PM alert** ("today: Friday-type / Monday-type / far put / no trade", expiry, reading time).
     - **About 3:05 PM run** that waits until 3:14 (3:29 from 7 Dec), fetches live data, and pushes exact strikes to my phone.
  3. After close: save 3:00 to 3:45 PM option minute data for the nearest 2 expiries to the repo, so the backtest can use real minute prices.
  4. A weekly report: actual vs expected, month-wise table, checklist updates.
- **HDFC Sky:** a broker plan offer (₹5,000 for 1,000 orders) wasn't worth it at 2 to 3 trades a week. Check real charges from a contract note.
- **Margin:** check the margin for naked far-OTM puts. Up to 3 to 4 positions can be open by Friday.
- **Open questions:**
  - The exact option closing-price window and settlement rules after 7 Dec; re-test once a few weeks of data exist.
  - Whether to drop or modify the Monday trade if its auction-era weakness continues.
