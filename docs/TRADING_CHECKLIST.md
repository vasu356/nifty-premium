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

**What the backtest says about which Nifty value to use** (`scripts/35_reference_timing.py`, Fri/Mon formula, net points):

| Nifty value used to choose strikes | Sep 2025 to Jul 2026 | Since 3 Aug 2026 |
|---|---|---|
| Live Nifty at 3:10 to 3:14 PM | +2,087 to +2,163 | +168 to +203 |
| Official close (used in the backtest; not knowable in time) | +2,133 | +624 |
| Options-implied Nifty (ATM strike + call − put) | +1,719 | +11 |

- **Before the auction era,** reading live Nifty at 3:10 to 3:20 PM gives the same result as the backtest.
- **Since 3 Aug,** the backtest figure is optimistic; the realistic result for Aug to Nov 2026 is about +170 to +250 over 27 trades.
- **Far puts** are not affected by which Nifty value you use.
- **Don't use the options-implied Nifty.**

### Daily timing

**Now, until 4 Dec 2026:**
1. **3:10 to 3:14 PM:** read live Nifty and S (the ATM call + put of the nearest expiry). Work out the strikes.
2. **3:15 to 3:35 PM:** sell, with limit orders near the middle of the bid and ask. Option prices keep trading normally during the auction, but Nifty is frozen until the auction close.
3. **Expiry Tuesday:** settlement is at the auction close, which can jump. Some days it has been 100 to 400 points away from 3:15 PM. If a short leg is within about 100 points of Nifty, or in the money, at 3:00 PM, buy it back before 3:15 PM rather than leave it to the auction.

**From Mon 7 Dec 2026:**
1. **3:20 to 3:28 PM:** read live Nifty and S, and work out the strikes.
2. **3:25 to 3:40 PM:** sell the new positions. F&O runs until 3:45 PM.
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

## B. Friday and Monday formula strangle (unchanged)

1. **Trend centre** = Nifty + 0.15 × (Nifty now − Nifty close 5 trading days ago).
2. **Call strike** = centre + 0.75 × S. **Put strike** = centre − 1.0 × S. Round each to the nearest 50.
3. **Sell 1 lot of each.**
   - **Friday's position:** buy both back at Monday's close, even at a small loss. Testing showed that holding a losing Friday position into Tuesday made things worse.
   - **Monday's position:** sell at the close and hold into Tuesday's expiry. If a leg is in the money near the close, buy it back.

**Worked example, Fri 13 Nov 2026:**
- Nifty 25,144.3. The close 5 trading days earlier (6 Nov) was 25,030.35, so centre = 25,144.3 + 0.15 × 113.95 = **25,161.4**.
- S = 136.85 + 135.95 = 272.8.
- Call target 25,161.4 + 204.6 = 25,366 → **sell 25350 CE at ₹62**.
- Put target 25,161.4 − 272.8 = 24,889 → **sell 24900 PE at ₹46.8**.

## C. Weekly picture and sizing

- **Max positions open:** by Friday night you can hold the Wednesday and Thursday puts, the Tuesday put if used, and the Friday strangle.
  All of them lose together in a crash week.
- **Worst weeks in testing:**
  - The worst full week for the formula plus far puts was **−694 points**, about **₹45,000 per lot**, from 26 Sep to 3 Oct 2024.
  - A single far put once went from ₹9 to ₹409 mid-week (Apr 2025) before recovering.
  - There has been no 2020-style crash since 2021, so a true crash could cost much more.
- **Start with Wed and Thu puts plus Fri and Mon, 1 lot each.** That's plan D: +3,834 points since Sep 2025, against +2,877 for the formula alone.
  Add the Tuesday put only after a few months, if margin allows.
- **Check HDFC Sky's margin** for a naked far-OTM put before starting. It needs its own margin per lot.
- **Charges:** the backtest assumed ₹65 per leg per lot. With far puts at only ₹6 to ₹10, a bad fill of ₹0.5 to ₹1 matters.
  Use limit orders near the mid price.

## D. What not to do (all tested and rejected)

- Overnight trades on Tue, Wed or Thu, or near-the-money strikes on those days.
- Fixed-premium strikes (₹20, ₹30, ₹50 and so on) instead of the formula.
- Buying options on Tuesday for a Wednesday exit (about break-even, needs a 150+ point move).
- Holding Friday's position into Tuesday; protective wings; next-week expiries; stop-losses on the far put.
