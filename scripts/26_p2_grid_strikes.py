"""Family A/B: strike distance grid and premium targets for the Fri (dte2) and Mon (dte1) overnight trades, P2 only."""
import sys, os, importlib, itertools, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
P = importlib.import_module("25_p2_lab")
OUT = P.OUT
G = [0.0, 0.25, 0.4, 0.5, 0.6, 0.75, 1.0, 1.25, 1.5]
rows, trades = [], []
for kc, kp, sh in itertools.product(G, G, (0.0, 0.15)):
    if kc == 0 and kp == 0 and sh:  # ATM straddle: no shift variant
        continue
    t = P.run(dict(dtes={1, 2}, exit="next", sel="S", kc=kc, kp=kp, sh=sh))
    for dte in (1, 2, None):
        s = t if dte is None else t[t.dte == dte]
        rows.append(dict(fam="S", kc=kc, kp=kp, sh=sh, day={1: "Mon", 2: "Fri", None: "both"}[dte], **P.summ(s)))
for X in (10, 15, 20, 25, 30, 40, 50, 60, 75, 100):
    t = P.run(dict(dtes={1, 2}, exit="next", sel="prem", X=X))
    for dte in (1, 2, None):
        s = t if dte is None else t[t.dte == dte]
        rows.append(dict(fam="prem", X=X, day={1: "Mon", 2: "Fri", None: "both"}[dte], **P.summ(s)))
R = pd.DataFrame(rows)
R.to_csv(os.path.join(OUT, "p2_grid_strikes.csv"), index=False, float_format="%.2f")
print("saved", len(R))
