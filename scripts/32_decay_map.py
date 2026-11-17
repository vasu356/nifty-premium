"""Decay map for mid-week selling. For every entry day with 3, 4 or 5 trading days to the nearest expiry
(Thu, Wed, Tue in the Tuesday-expiry era; Mon, Fri, Thu before Sep 2025), for each side (CE/PE) and strike distance
m x S from spot (S = ATM straddle of that expiry at entry), record the short leg's value at every later close up to expiry
(intrinsic on expiry day). Output: results/manual/decay_map_legs.csv.gz (one row per entry x side x distance)."""
import os, sys, importlib
import numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "results", "manual")
L = labm.Lab(start="2020-11-15")
M = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0]
rows = []
for i, d in enumerate(L.days[:-1]):
    if d < "2021-01-04":
        continue
    e = L.expiry(d)
    if e is None or e > L.days[-1]:
        continue
    n = L.dte(d, e)
    if n not in (3, 4, 5):
        continue
    at = L.atm(d, e)
    if at is None:
        continue
    S = at[1] + at[2]; sp = L.spot[d]
    path = [x for x in L.days[i + 1:] if x <= e]
    if not path or path[-1] != e:
        continue
    for o in ("CE", "PE"):
        for m in M:
            r = L.by_strike(d, e, o, sp + m * S if o == "CE" else sp - m * S)
            if r is None:
                continue
            k, c = r
            if c <= 0:
                continue
            row = dict(sell=d, expiry=e, dte=n, spot=sp, S=S, side=o, m=m, k=k, credit=c)
            ok = True
            for h, x in enumerate(path, 1):
                if x == e:
                    v = max(0.0, L.spot[x] - k) if o == "CE" else max(0.0, k - L.spot[x])
                else:
                    q = L.q(x, e, o, k)
                    if q is None:
                        ok = False; break
                    v = q["close"]
                row[f"v{h}"] = v; row[f"d{h}"] = x
            if ok:
                rows.append(row)
T = pd.DataFrame(rows)
T.to_csv(os.path.join(OUT, "decay_map_legs.csv.gz"), index=False, float_format="%.3f")
print(len(T), "leg rows;", T.sell.nunique(), "entry days")
print(T.groupby([np.where(T.sell >= "2025-09-01", "P2", "P1"), "dte"]).sell.nunique())
