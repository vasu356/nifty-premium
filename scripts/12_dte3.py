"""Does a 3rd weekly trade (3 trading days before expiry) add value? Grid over settings for that day only.
Charges: 2 points per 2-leg trade. Periods as in 10_search."""
import os, sys, importlib, itertools
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
S = importlib.import_module("10_search"); labm = importlib.import_module("08_strategy_lab")
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "manual")
L = labm.Lab(start="2020-11-15")

def run(kw):
    t = L.run(S.builder(**kw), S.OLD[0]); t["net"] = t.total - S.CHARGE_PER_LEG * t.legs.str.count("/").add(1); return t

def ev(t):
    if len(t) == 0: return dict(n=0, net=0, dd=0, rdd=np.nan, worst=np.nan, win=np.nan)
    eq = t.net.cumsum(); dd = (eq - eq.cummax()).min()
    return dict(n=len(t), net=t.net.sum(), dd=dd, rdd=t.net.sum() / abs(dd) if dd < 0 else np.inf, worst=t.net.min(), win=(t.net > 0).mean())

def split(t):
    return t[t.sell <= S.OLD[1]], t[t.sell >= S.NEW[0]]

# current best (days 1-2)
G = run(dict(mc=0.75, mp=1.0, shift=0.15))
rows = []
filters = {"none": None, "skip_cheap 0.005": S.make_filter("skip_cheap", 0.005), "skip_cheap 0.006": S.make_filter("skip_cheap", 0.006),
           "skip_rich 0.012": S.make_filter("skip_rich", 0.012), "skip_prev_move 150": S.make_filter("skip_prev_move", 150),
           "skip_big_week 400": S.make_filter("skip_after_big_week", 400)}
for mc, mp, sh, (fn, ff) in itertools.product((0.75, 1.0, 1.25, 1.5, 2.0, 2.5), (1.0, 1.25, 1.5, 2.0, 2.5), (0.0, 0.15), filters.items()):
    t3 = run(dict(mc=mc, mp=mp, shift=sh, dtes={3}, filt=ff))
    o3, n3 = split(t3)
    both = pd.concat([G, t3]).sort_values("sell"); ob, nb = split(both)
    rows.append(dict(mc=mc, mp=mp, shift=sh, filt=fn,
                     **{f"d3old_{k}": v for k, v in ev(o3).items()}, **{f"d3new_{k}": v for k, v in ev(n3).items()},
                     **{f"comb_old_{k}": v for k, v in ev(ob).items()}, **{f"comb_new_{k}": v for k, v in ev(nb).items()},
                     y_pos=int((t3.groupby(t3.sell.str[:4]).net.sum() > 0).sum()) if len(t3) else 0))
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, "dte3_grid.csv"), index=False, float_format="%.3f")
go, gn = split(G); print("G only OLD", {k: round(v, 2) for k, v in ev(go).items()}); print("G only NEW", {k: round(v, 2) for k, v in ev(gn).items()})
