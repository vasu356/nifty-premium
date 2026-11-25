"""Final realistic grid (Nov 2026 data refresh, data to 23 Nov 2026).

Realistic inputs: Nifty = live 1-minute close at 15:14 (last live minute in the closing-auction era; earlier eras fine too);
trend = 0.15-type shift on (live 15:14 - official close 5 trading days ago); S = ATM straddle from NSE closing prices;
trade prices = NSE closing prices (30-min VWAP); expiry legs settle at intrinsic on the official close. Charges 1 pt per leg.
Components (nearest weekly expiry, counted in trading days to expiry, dte):
  FRI  dte 2 strangle, exit next close        grid kc x kp x sh
  MON  dte 1 strangle, into expiry            grid kc x kp x sh
  PUTd dte 3/4/5 far put held to expiry       m in 1.5..3.0
  CALLd dte 3/4/5 far call held to expiry     m in 2.0..3.0
Writes results/manual/final_grid_trades.csv.gz (every trade of every variant)."""
import os, sys, importlib, itertools, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "results", "manual")
L = labm.Lab(start="2020-11-15")
m1 = pd.read_csv(os.path.join(ROOT, "data", "market", "nifty_1min_combined.csv"))
LIVE = dict(zip(m1[m1.datetime.str[11:16] == "15:14"].datetime.str[:10], m1[m1.datetime.str[11:16] == "15:14"].close))
SETTLE = {}
def settle_day(e):
    if e not in SETTLE: SETTLE[e] = max(x for x in L.days if x <= e)
    return SETTLE[e]
def val(x, e, o, k):
    if x == settle_day(e):
        s = L.spot[x]; return max(0.0, s - k) if o == "CE" else max(0.0, k - s)
    q = L.q(x, e, o, k); return None if q is None else q["close"]
KC, KP, SH = (0.25, 0.5, 0.75, 1.0), (0.75, 1.0, 1.25, 1.5), (0.0, 0.15, 0.3)
rows = []
for i, d in enumerate(L.days[:-1]):
    if d < "2021-01-04" or d not in LIVE: continue
    e = L.expiry(d)
    if e is None or settle_day(e) > L.days[-1] or settle_day(e) <= d: continue
    n = L.dte(d, e)
    if n > 5: continue
    at = L.atm(d, e)
    if at is None: continue
    S = at[1] + at[2]; sp = LIVE[d]; j = L.allidx.index(d); ch = sp - L.idx.close.iloc[j - 5]
    base = dict(sell=d, expiry=e, dte=n, S=S, spot=sp)
    if n in (1, 2):
        comp = "MON" if n == 1 else "FRI"; x = L.days[i + 1]
        for kc, kp, sh in itertools.product(KC, KP, SH):
            c = sp + sh * ch
            ce = L.by_strike(d, e, "CE", max(c + kc * S, sp)); pe = L.by_strike(d, e, "PE", min(c - kp * S, sp))
            if ce is None or pe is None: continue
            a, b = val(x, e, "CE", ce[0]), val(x, e, "PE", pe[0])
            if a is None or b is None: continue
            rows.append(dict(base, comp=comp, var=f"call {kc} / put {kp} / shift {sh}", credit=ce[1] + pe[1], net=ce[1] + pe[1] - a - b - 2))
    else:
        sd = settle_day(e); day = {3: "THU", 4: "WED", 5: "TUE"}[n]
        for mm in (1.5, 2.0, 2.5, 3.0):
            pe = L.by_strike(d, e, "PE", sp - mm * S)
            if pe and pe[1] > 0: rows.append(dict(base, comp=f"PUT {day}", var=f"put {mm}xS", credit=pe[1], net=pe[1] - val(sd, e, "PE", pe[0]) - 1))
        for mm in (2.0, 2.5, 3.0):
            ce = L.by_strike(d, e, "CE", sp + mm * S)
            if ce and ce[1] > 0: rows.append(dict(base, comp=f"CALL {day}", var=f"call {mm}xS", credit=ce[1], net=ce[1] - val(sd, e, "CE", ce[0]) - 1))
T = pd.DataFrame(rows)
T.to_csv(os.path.join(OUT, "final_grid_trades.csv.gz"), index=False, float_format="%.3f")
print(len(T), "trade rows;", T.sell.min(), "->", T.sell.max()); print(T.groupby("comp")["var"].nunique().to_dict())
