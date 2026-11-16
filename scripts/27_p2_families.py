"""Families C-F on P2: hold-to-expiry from earlier days, stops, wings (iron condors), one-sided, next-week expiry."""
import sys, os, importlib, itertools, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
P = importlib.import_module("25_p2_lab")
rows = []
def add(fam, spec, **lab):
    t = P.run(spec)
    rows.append(dict(fam=fam, **lab, **P.summ(t)))
    return t
K = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0]
# C: hold to expiry, entry dte 2..5 (Fri, Thu, Wed, Tue), stops none / 2x / 3x credit (checked at daily closes)
for dte, kc, kp, st in itertools.product((2, 3, 4, 5), K, K, (None, 2.0, 3.0)):
    if abs(kc - kp) > 0.5: continue
    add("C_hold", dict(dtes={dte}, exit="expiry", sel="S", kc=kc, kp=kp, sh=0.15, stop=st), dte=dte, kc=kc, kp=kp, stop=st)
# C2: overnight trades on dte 3..5 for reference with same grid (no stop)
for dte, kc, kp in itertools.product((3, 4, 5), K, K):
    if abs(kc - kp) > 0.5: continue
    add("C_night", dict(dtes={dte}, exit="next", sel="S", kc=kc, kp=kp, sh=0.15), dte=dte, kc=kc, kp=kp)
# D: wings on Fri/Mon overnight
for (kc, kp), w in itertools.product(((0.0, 1.0), (0.25, 1.0), (0.5, 0.75), (0.75, 1.0), (0.5, 0.5)), (0.25, 0.5, 1.0, 1.5)):
    add("D_wing", dict(dtes={1, 2}, exit="next", sel="S", kc=kc, kp=kp, sh=0.15, wing=w), kc=kc, kp=kp, wing=w)
# E: one-sided Fri/Mon overnight
for k in (0.0, 0.25, 0.5, 0.75, 1.0, 1.25):
    add("E_put", dict(dtes={1, 2}, exit="next", sel="S", kc=0, kp=k, sh=0.15, sides=("PE",)), kp=k)
    add("E_call", dict(dtes={1, 2}, exit="next", sel="S", kc=k, kp=0, sh=0.15, sides=("CE",)), kc=k)
# F: next-week expiry, one night, every day
for kc, kp in ((0.5, 0.75), (0.75, 1.0), (1.0, 1.25), (1.25, 1.5)):
    add("F_nextwk", dict(dtes=set(range(5, 11)), exit="next", sel="S", kc=kc, kp=kp, sh=0.15, ek=1), kc=kc, kp=kp)
R = pd.DataFrame(rows); R.to_csv(os.path.join(P.OUT, "p2_families.csv"), index=False, float_format="%.2f"); print("saved", len(R))
