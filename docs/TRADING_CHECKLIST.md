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

All entries are at the **close**, around 3:20 to 3:25 PM. The backtest used NSE's official closing prices, which are the
average of the last 30 minutes, so live prices will differ a little.

## Step 0: two numbers to read at about 3:20 PM

1. **Nifty** (the spot index level now).
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
