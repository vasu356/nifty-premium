"""Friday/Monday formula report from Sep 2025, realistic inputs (live 15:14 Nifty; centre = Nifty + 0.15*(Nifty - official close
5 trading days ago); S = ATM straddle from NSE closing prices). Fri-type (dte 2): call c+0.75S, put c-1.0S, exit next close.
Mon-type (dte 1): call c+0.5S, put c-1.0S, settled at intrinsic on the expiry close. Net of 2 points (Rs 130) per trade."""
import os, sys, importlib, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pd.set_option("display.width", 260); pd.set_option("display.max_rows", 300)
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
    if n not in (1, 2): continue
    at = L.atm(d, e); S = at[1] + at[2]; sp = LIVE[d]; j = L.allidx.index(d); c = sp + 0.15 * (sp - L.idx.close.iloc[j - 5])
    kc = 0.75 if n == 2 else 0.5
    ce = L.by_strike(d, e, "CE", max(c + kc * S, sp)); pe = L.by_strike(d, e, "PE", min(c - 1.0 * S, sp))
    credit = ce[1] + pe[1]
    if i + 1 >= len(L.days):
        rows.append(dict(sell=d, type="Fri" if n == 2 else "Mon", expiry=e, exit="(open)", nifty_314=sp, S=round(S, 1), call=int(ce[0]), put=int(pe[0]),
                         credit=round(credit, 2), buyback=np.nan, ce_pnl=np.nan, pe_pnl=np.nan, move=np.nan, net=np.nan)); continue
    x = L.days[i + 1]
    if x == settle_day(e):
        s = L.spot[x]; vc, vp = max(0.0, s - ce[0]), max(0.0, pe[0] - s)
    else:
        vc, vp = L.q(x, e, "CE", ce[0])["close"], L.q(x, e, "PE", pe[0])["close"]
    rows.append(dict(sell=d, type="Fri" if n == 2 else "Mon", expiry=e, exit=x, nifty_314=sp, S=round(S, 1), call=int(ce[0]), put=int(pe[0]),
                     credit=round(credit, 2), buyback=round(vc + vp, 2), ce_pnl=round(ce[1] - vc, 1), pe_pnl=round(pe[1] - vp, 1),
                     move=round(L.spot[x] - L.spot[d], 1), net=round(credit - vc - vp - 2, 2)))
T = pd.DataFrame(rows); T["wd"] = pd.to_datetime(T.sell).dt.day_name().str[:3]
print("=== Every trade (type by trading days to expiry; holiday weeks shift the weekday)")
print(T[["sell", "wd", "type", "expiry", "exit", "nifty_314", "S", "call", "put", "credit", "buyback", "ce_pnl", "pe_pnl", "move", "net"]].to_string(index=False))
s = T.dropna(subset=["net"])
W = s.pivot_table(index="expiry", columns="type", values="net", aggfunc="sum").round(1).fillna(0); W["total"] = W.sum(axis=1); W["rupees"] = (W.total * 65).round(0); W["cumulative"] = W.total.cumsum().round(1)
print("\n=== Weekly (by expiry)"); print(W.to_string())
s = s.assign(month=s.sell.str[:7])
M = s.pivot_table(index="month", columns="type", values="net", aggfunc="sum").round(1); M["total"] = M.sum(axis=1)
M["wins"] = s.groupby("month").net.apply(lambda v: f"{(v > 0).sum()}/{len(v)}"); M["rupees"] = (M.total * 65).round(0); M["cumulative"] = M.total.cumsum().round(1)
print("\n=== Monthly"); print(M.to_string())
for t in ("Fri", "Mon"):
    v = s[s.type == t].net; print(f"{t}: trades {len(v)} wins {(v>0).sum()} total {v.sum():.1f} (Rs {v.sum()*65:,.0f}) avg {v.mean():.1f} median {v.median():.1f} worst {v.min():.1f} best {v.max():.1f}")
v = s.net; print(f"ALL: trades {len(v)} wins {(v>0).sum()} total {v.sum():.1f} (Rs {v.sum()*65:,.0f}) avg {v.mean():.1f} worst week {W.total.min():.1f}  weeks negative {(W.total<0).sum()}/{len(W)}")
T.to_csv(os.path.join(ROOT, "results", "manual", "fri_mon_trades.csv"), index=False)
