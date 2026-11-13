"""Combine the two robust improvements (asymmetric distance + trend-shifted centre),
optionally with separate settings for 1 and 2 days before expiry.
Settings are chosen on 2021-01..2025-08 ONLY, then tested on 2025-09..2026-11."""
import os, sys, importlib, itertools
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
S = importlib.import_module("10_search"); labm = importlib.import_module("08_strategy_lab")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "manual")
L = labm.Lab(start="2020-11-15")

def trades(kw):
    t = L.run(S.builder(**kw), S.OLD[0])
    t["net"] = t.total - S.CHARGE_PER_LEG * t.legs.str.count("/").add(1)
    return t

def ev(t):
    eq = t.net.cumsum(); dd = (eq - eq.cummax()).min()
    m = t.groupby(t.sell.str[:7]).net.sum()
    return dict(n=len(t), net=t.net.sum(), dd=dd, rdd=t.net.sum() / abs(dd), worst=t.net.min(), win=(t.net > 0).mean(), mpos=(m > 0).mean())

grid = list(itertools.product((0.5, 0.6, 0.75, 0.9, 1.0), (0.75, 0.9, 1.0, 1.25, 1.5), (0.0, 0.15, 0.25, 0.35), (1, 2)))
rows, cache = [], {}
for mc, mp, sh, d in grid:
    t = trades(dict(mc=mc, mp=mp, shift=sh, shift_n=5, dtes={d}))
    cache[(mc, mp, sh, d)] = t
    o, n = ev(t[t.sell <= S.OLD[1]]), ev(t[t.sell >= S.NEW[0]])
    rows.append(dict(mc=mc, mp=mp, shift=sh, dte=d, **{f"old_{k}": v for k, v in o.items()}, **{f"new_{k}": v for k, v in n.items()}))
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, "walkforward_grid.csv"), index=False, float_format="%.3f")
pd.set_option("display.width", 250)
for d in (1, 2):
    g = R[R.dte == d].sort_values("old_rdd", ascending=False)
    print(f"\n=== DTE {d}: top 10 chosen on OLD (ranked by net/biggest drop) ===")
    print(g.head(10).round(2).to_string(index=False))

# walk-forward pick: best OLD ret/dd for each day, combined
pick = {d: R[R.dte == d].sort_values("old_rdd", ascending=False).iloc[0] for d in (1, 2)}
comb = pd.concat([cache[(p.mc, p.mp, p["shift"], d)] for d, p in pick.items()]).sort_values("sell")
comb.to_csv(os.path.join(OUT, "walkforward_pick_trades.csv"), index=False, float_format="%.2f")
base = pd.concat([cache[(1.0, 1.0, 0.0, 1)], cache[(1.0, 1.0, 0.0, 2)]]).sort_values("sell")
print("\nPICK:", {d: (p.mc, p.mp, p["shift"]) for d, p in pick.items()})
for name, t in (("BASE 1.0/1.0/no shift", base), ("WALK-FORWARD PICK", comb)):
    print(name, "OLD", {k: round(v, 2) for k, v in ev(t[t.sell <= S.OLD[1]]).items()})
    print(name, "NEW", {k: round(v, 2) for k, v in ev(t[t.sell >= S.NEW[0]]).items()})
