"""Wednesday/Thursday far-put report (put = live 15:14 Nifty - 2.5 x S, nearest expiry, held to expiry, net of 1 point charge).
Weekly (by expiry) and monthly from Sep 2025; positions whose expiry is after the last data day are marked at the latest close."""
import os, sys, importlib, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
L = labm.Lab(start="2025-06-01")
m1 = pd.read_csv(os.path.join(ROOT, "data", "market", "nifty_1min_combined.csv")); m1 = m1[m1.datetime.str[11:16] == "15:14"]
LIVE = dict(zip(m1.datetime.str[:10], m1.close)); LAST = L.days[-1]
def settle_day(e): return max(x for x in L.days if x <= e)
rows = []
for i, d in enumerate(L.days):
    if d < "2025-09-01" or d not in LIVE: continue
    e = L.expiry(d)
    if e is None: continue
    n = L.dte(d, e)
    if n not in (3, 4): continue
    at = L.atm(d, e); S = at[1] + at[2]; sp = LIVE[d]
    k, cr = L.by_strike(d, e, "PE", sp - 2.5 * S)
    if e <= LAST:
        sd = settle_day(e); v = max(0.0, k - L.spot[sd]); status = "settled"; low = min(L.spot[x] for x in L.days if d < x <= sd)
    else:
        q = L.q(LAST, e, "PE", k); v = q["close"]; status = f"open (marked {LAST})"; low = min(L.spot[x] for x in L.days if d < x <= LAST)
    rows.append(dict(sell=d, day="Wed" if n == 4 else "Thu", expiry=e, nifty_314=sp, S=round(S, 1), strike=int(k), dist=round(sp - k), premium=cr,
                     value_at_exit=round(v, 2), net=round(cr - v - 1, 2), nifty_low_close=round(low), cushion=round(low - k), status=status))
T = pd.DataFrame(rows); T["rupees"] = (T.net * 65).round(0)
print("=== Every trade (Wed = 4 trading days to expiry, Thu = 3; holiday weeks shift the weekday)")
print(T[["sell", "day", "expiry", "nifty_314", "S", "strike", "dist", "premium", "value_at_exit", "net", "cushion", "status"]].to_string(index=False))
W = T.groupby("expiry").agg(trades=("net", "size"), premium=("premium", "sum"), net=("net", "sum")).round(1); W["rupees"] = (W.net * 65).round(0); W["cumulative"] = W.net.cumsum().round(1)
print("\n=== Weekly (by expiry), Wed + Thu puts combined"); print(W.to_string())
T["month"] = T.sell.str[:7]
M = T.pivot_table(index="month", columns="day", values="net", aggfunc="sum").round(1); M["total"] = M.sum(axis=1); M["trades"] = T.groupby("month").size()
M["wins"] = T.groupby("month").net.apply(lambda s: f"{(s > 0).sum()}/{len(s)}"); M["rupees"] = (M.total * 65).round(0); M["cumulative"] = M.total.cumsum().round(1)
print("\n=== Monthly"); print(M.to_string())
s = T[T.status == "settled"]
print(f"\nSettled trades: {len(s)}  wins {(s.net > 0).sum()}  losses {(s.net <= 0).sum()}  total {s.net.sum():.1f} pts (Rs {s.net.sum()*65:,.0f})  avg {s.net.mean():.2f}  worst {s.net.min():.1f}  "
      f"avg premium {s.premium.mean():.1f}  expired worthless {(s.value_at_exit == 0).mean()*100:.0f}%  avg distance {s.dist.mean():.0f} pts")
print("By day:", s.groupby("day").net.agg(["size", "sum", "mean", "min"]).round(1).to_dict("index"))
T.to_csv(os.path.join(ROOT, "results", "manual", "far_put_wed_thu_trades.csv"), index=False)
