"""Option BUYING test: buy at the close of expiry day (Tuesday since Sep 2025, Thursday before), sell at the next day's
OPEN, next day's CLOSE, or the close two days later. Expiry bought: next weekly (ek=0, ~5 trading days) or the one after (ek=1, ~10).
Strikes: multiples of that expiry's ATM straddle S around spot (negative = in the money) or premium targets.
Charges: 1 point per leg (Rs 130 per 2-leg round trip at 65 units). Prices: NSE open (first trade) / close.
Output: results/manual/buy_trades.csv.gz (one row per trade x variant)."""
import os, sys, importlib, itertools
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "results", "manual")
L = labm.Lab(start="2020-11-15")
EXPIRIES = set(e for d in L.exps for e in L.exps[d])
ENTRY = [d for d in L.days[:-3] if d in EXPIRIES and d >= "2021-01-04"]      # expiry days


def leg(d, e, o, mode, val, S, sp):
    if mode == "S":                      # strike = spot +/- val*S (val<0 -> in the money)
        tgt = sp + val * S if o == "CE" else sp - val * S
        return L.by_strike(d, e, o, tgt)
    return L.by_price(d, e, o, val, otm_of=sp)  # premium target, out of the money


def px(x, e, o, k, f):
    q = L.q(x, e, o, k)
    if q is None:
        return None, 0
    if f == "open":
        if q["open"] > 0 and q["contracts"] > 0:
            return q["open"], 0
        return q["close"], 1          # no trade at open: fall back to close (flagged)
    return q["close"], 0


rows = []
STRIKES = [("S", v) for v in (-0.5, -0.25, 0.0, 0.25, 0.5, 0.75, 1.0, 1.5)] + [("P", v) for v in (10, 20, 30, 50, 75, 100, 150)]
for d in ENTRY:
    i = L.pos[d]
    sp = L.spot[d]
    x1, x2 = L.days[i + 1], L.days[i + 2]
    for ek in (0, 1):
        e = L.expiry(d, k=ek)
        if e is None or e <= x2:
            continue
        at = L.atm(d, e)
        if at is None:
            continue
        S = at[1] + at[2]
        for mode, val in STRIKES:
            if mode == "S" and val == 0.0:
                ce = (at[0], at[1]); pe = (at[0], at[2])
            else:
                ce = leg(d, e, "CE", mode, val, S, sp); pe = leg(d, e, "PE", mode, val, S, sp)
            for o, r in (("CE", ce), ("PE", pe)):
                if r is None:
                    continue
                k, cost = r
                if cost <= 0:
                    continue
                out = dict(sell=d, wd=pd.Timestamp(d).day_name()[:3], ek=ek, expiry=e, dte=L.dte(d, e), spot=sp, S=S, mode=mode, val=val, opt=o, k=k, cost=cost)
                for lab, x, f in (("wo", x1, "open"), ("wc", x1, "close"), ("tc", x2, "close")):
                    p, fb = px(x, e, o, k, f)
                    out[lab] = np.nan if p is None else p - cost
                    out[lab + "_fb"] = fb
                out["mv_open"] = L.spot_open[x1] - sp; out["mv_wc"] = L.spot[x1] - sp; out["mv_tc"] = L.spot[x2] - sp
                rows.append(out)
T = pd.DataFrame(rows)
T.to_csv(os.path.join(OUT, "buy_trades.csv.gz"), index=False, float_format="%.3f")
print(len(T), "leg-rows;", T.sell.nunique(), "entry days", T.sell.min(), "->", T.sell.max())
print(T.groupby(T.sell.str[:4]).sell.nunique().to_dict(), T.wd.value_counts().to_dict())
