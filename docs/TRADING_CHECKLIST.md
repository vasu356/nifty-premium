# Weekly Nifty option-selling checklist

Weekly Nifty expiry is on **Tuesday** (Monday when Tuesday is a holiday). All trades use the **nearest weekly expiry**.
Days are counted in **trading days before expiry**, so holidays move the trade days automatically.

| Trading days before expiry | Normal weekday | Trade |
|---|---|---|
| 5 | Tuesday (the previous expiry day) | Far put (optional, add later) |
| 4 | Wednesday | Far put |
| 3 | Thursday | Far put |
| 2 | Friday | Formula strangle, overnight |
| 1 | Monday | Formula strangle, into expiry |

## Timing: market rules changed in 2026 (researched 17 Nov 2026)

NSE now ends the cash market with a **closing auction session (CAS)**. Nifty's official close is computed from the auction,
so it is only known after the auction ends, after you have already traded. Secondary sources agree on the timings below;
the NSE circulars could not be opened from this session, so check them in your broker app.

| | **Now, until Fri 4 Dec 2026** (since 3 Aug 2026) | **From Mon 7 Dec 2026** |
|---|---|---|
| Normal trading in Nifty stocks (live Nifty updates) | until **3:15 PM** | until **3:30 PM** |
| Closing auction (Nifty frozen, then jumps to the auction close) | 3:15 to about 3:35 PM | 3:30 to 3:40 PM, matching 3:40 to 3:45 |
| F&O trading ends | **3:40 PM** | **3:45 PM** (expiry day: contracts expiring that day stop at **3:30 PM**) |
| Option "closing price" used in our data | average of 3:10 to 3:40 PM | an average of the last 30 minutes (window not confirmed) |
| Expiry settlement of index options | Nifty's auction-based close (most sources) | **30-minute average of normal trading** (auction price no longer used) |

**What the backtest says about which Nifty value to use** (`scripts/36_reference_minute_test.py`, Fri/Mon formula, net points):

| Nifty value used to choose strikes | 2021 to Aug 2025 | Sep 2025 to Jul 2026 | Since 3 Aug 2026 (29 trades) |
|---|---|---|---|
| Live Nifty at 2:30 PM | +4,115 | +1,458 | +249 |
| Live Nifty at 3:00 PM | +4,152 | +1,914 | +252 |
| Live Nifty at 3:05 to 3:14 PM | +4,397 to +5,242 | +2,087 to +2,181 | +137 to +272 |
| Live Nifty at 3:20 to 3:29 PM (not available since Aug) | +5,260 to +5,483 | +1,825 to +2,104 | — |
| Official close (backtest; known only after you trade) | +5,011 | +2,133 | +624 |
| Options-implied Nifty (ATM strike + call − put) | +4,615 | +1,719 | +11 |

- **Read Nifty as late as possible while it is still live.** Readings from 3:05 PM on match the official close in both older periods;
  readings at 2:30 to 3:00 PM are clearly worse.
- **Since 3 Aug, the last live reading is 3:14 PM.** Live Nifty stops then, and the next print is the auction close at about 3:28 to 3:29.
  The backtest's +624 for that period used a close you can't know in time; realistically it was about +140 to +270.
- **Don't use the options-implied Nifty.** It is the worst in every period: picking strikes from the same prices you sell at tilts you
  towards the relatively cheaper side.
- **Far puts** don't depend on which reading you use (they're too far away).
- **Why Aug to Nov 2026 was weak:** more big moves (31% of nights moved more than S, against 21% before), mostly in Oct 2026.
  Monday trades made only +1 per trade, against +30 before. The auction itself had a small net effect on expiry day
  (+29 points over 15 Mondays). The far puts were about break-even since Aug (+15 to +25 over 28 trades).

### Daily timing

**Now, until 4 Dec 2026:**
1. **3:12 to 3:14 PM:** read live Nifty and S (the ATM call + put of the nearest expiry). Work out the strikes.
2. **3:15 to 3:35 PM:** sell, with limit orders near the middle of the bid and ask. Option prices keep trading normally during the auction, but Nifty is frozen until the auction close.
3. **Expiry Tuesday:** settlement is at the auction close, which can jump. Some days it has been 100 to 400 points away from 3:15 PM. If a short leg is within about 100 points of Nifty, or in the money, at 3:00 PM, buy it back before 3:15 PM rather than leave it to the auction.

**From Mon 7 Dec 2026:**
1. **3:25 to 3:29 PM:** read live Nifty and S, and work out the strikes.
2. **3:30 to 3:40 PM:** sell the new positions. F&O runs until 3:45 PM.
3. **Expiry Tuesday:** the expiring contracts stop at 3:30 PM and settle on a 30-minute average, which is smoother. If you want to buy back a leg, do it before 3:30 PM.

**For the 5-day trend term:** use the official Nifty close of the day 5 trading days back, from NSE or your broker's daily chart.

## Step 0: two numbers to read (see Timing above)

1. **Nifty** (the live spot index level, at the time given in the Timing section).
2. **S, the ATM straddle of the nearest expiry**: the Nifty strike nearest to spot, call premium + put premium.
   - Example from 12 Nov 2026: Nifty 25,299.35, ATM 25300, call 174.85 + put 190.35, so **S = 365.2**.

Strikes are in steps of 50. Round to the nearest 50; if exactly halfway, take the strike **further** from Nifty.

## A. Far put on Wednesday and Thursday (Tuesday optional)

1. Put strike target = **Nifty − 2.5 × S**. Round to the nearest 50.
2. **Sell 1 lot of that put.** No call.
3. **Hold to expiry** and let it expire. Don't stop out on a scary mid-week spike: in testing, stops made results worse.
   - If it is in the money in the last minutes of expiry day, buy it back at the close instead of letting it settle.
4. What to expect (Sep 2025 to Nov 2026, middle values):

   | Entry | Distance below Nifty | Premium |
   |---|---|---|
   | Thu | ~630 pts (2.6%) | ~₹8 |
   | Wed | ~740 pts (3.0%) | ~₹9.5 |
   | Tue | ~780 pts (3.1%) | ~₹9.5 |

   About 97% expire worthless. Average net was +8 to +11 points per trade since Sep 2025, and +5 to +7 in 2021 to 2025.

**Worked examples:**
- **Wed 11 Nov 2026:** Nifty 25,255.05, S = 465.1. Target 25,255 − 1,163 = 24,092, so **sell 24100 PE at ₹10.15**.
- **Thu 12 Nov 2026:** Nifty 25,299.35, S = 365.2. Target 25,299 − 913 = 24,386, so **sell 24400 PE at ₹5.85**.

## B. Friday and Monday formula strangle

1. **Trend centre** = Nifty + 0.15 × (Nifty now − Nifty close 5 trading days ago).
2. **Friday:** call strike = centre + **0.75** × S. Put strike = centre − 1.0 × S. Round each to the nearest 50.
   **Monday:** call strike = centre + **0.5** × S (slightly closer). Put strike = centre − 1.0 × S.
   - Why Monday is different (`scripts/37_grid_live_reading.py`, strikes from live 3:14 PM Nifty): the closer Monday call gained
     +479, +157 and +114 points in the three periods (2021 to Aug 2025, Sep 2025 to Jul 2026, since Aug 2026), and +724 overall over 610 trades,
     with a 96% chance the gain is real. On Fridays it made no difference. The cost is a slightly deeper drawdown (−731 against −641).
3. **Sell 1 lot of each.**
   - **Friday's position:** buy both back at Monday's close, even at a small loss. Testing showed that holding a losing Friday position into Tuesday made things worse.
   - **Monday's position:** sell at the close and hold into Tuesday's expiry. If a leg is in the money near the close, buy it back.

**Worked example, Fri 13 Nov 2026** (S uses NSE closing prices, since we don't have the 3:14 PM option prices):
- Live Nifty at 3:14 PM was 25,139.95. The official close 5 trading days earlier (6 Nov) was 25,030.35,
  so centre = 25,139.95 + 0.15 × 109.6 = **25,156.4**.
- S = 136.85 + 135.95 = 272.8.
- Call target 25,156.4 + 204.6 = 25,361 → **sell 25350 CE at ₹62**.
- Put target 25,156.4 − 272.8 = 24,884 → **sell 24900 PE at ₹46.8**.
- On a Monday the call target would be centre + 0.5 × S instead.

## C. Weekly picture and sizing

- **Max positions open:** by Friday night you can hold the Wednesday and Thursday puts, the Tuesday put if used, and the Friday strangle.
  All of them lose together in a crash week.
- **Worst weeks in testing:**
  - The worst full week for the formula plus far puts was **−694 points**, about **₹45,000 per lot**, from 26 Sep to 3 Oct 2024.
  - A single far put once went from ₹9 to ₹409 mid-week (Apr 2025) before recovering.
  - There has been no 2020-style crash since 2021, so a true crash could cost much more.
- **Start with Wed and Thu puts plus Fri and Mon, 1 lot each** (plan C). Realistic backtest, strikes from the live 3:14 PM Nifty,
  1 Sep 2025 to 23 Nov 2026 (`scripts/40_final_plans.py`):

  | Plan | Net points | ₹ at 65 units | Worst week | Months positive | Since 3 Aug 2026 |
  |---|---|---|---|---|---|
  | A original (Fri + Mon 0.75 / 1.0) | +2,135 | ₹1.39L | −426 | 12/15 | −13 |
  | B Fri 0.75 + Mon call 0.5 | +2,330 | ₹1.51L | −459 | 12/15 | +64 |
  | **C = B + far puts Wed, Thu** | **+3,287** | **₹2.14L** | −433 | 12/15 | +109 |
  | D = C + far put Tue | +3,763 | ₹2.45L | −419 | 12/15 | +215 |

  Add the Tuesday put only after a few months, if margin allows.
- **Holiday weeks shift every trade one day earlier.** Example: Tue 24 Nov 2026 was a holiday, so expiry was Mon 23 Nov.
  The Friday-type trade (2 days before expiry) was placed on Thu 19 Nov, and the Monday-type trade (1 day before) on Fri 20 Nov.
- **Check HDFC Sky's margin** for a naked far-OTM put before starting. It needs its own margin per lot.
- **Charges:** the backtest assumed ₹65 per leg per lot. With far puts at only ₹6 to ₹10, a bad fill of ₹0.5 to ₹1 matters.
  Use limit orders near the mid price.

## D. What not to do (all tested and rejected)

- Overnight trades on Tue, Wed or Thu, or near-the-money strikes on those days.
- Fixed-premium strikes (₹20, ₹30, ₹50 and so on) instead of the formula.
- Buying options on Tuesday for a Wednesday exit (about break-even, needs a 150+ point move).
- Holding Friday's position into Tuesday; protective wings; next-week expiries; stop-losses on the far put.
