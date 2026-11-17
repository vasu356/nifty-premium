"""Fri/Mon formula multiplier grid with strikes chosen from the live 15:14 Nifty (the last live reading in the auction era).
Eras as in 36_reference_minute_test.py. Net of 2 points per trade."""
import sys, os, importlib, itertools, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab"); L = labm.Lab(start="2020-11-15")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pd.set_option("display.width", 260)
m = pd.read_csv(os.path.join(ROOT, "data", "market_user", "nifty50_1min.csv")); m = m[m.datetime.str[11:16] == "15:14"]
p314 = dict(zip(m.datetime.str[:10], m.close))
def settle_day(e): return max(x for x in L.days if x <= e)
def val(x, e, o, k):
    if x == settle_day(e): s = L.spot[x]; return max(0, s - k) if o == "CE" else max(0, k - s)
    q = L.q(x, e, o, k); return None if q is None else q["close"]
KC, KP, SH = (0.5, 0.75, 1.0, 1.25), (0.75, 1.0, 1.25, 1.5), (0.0, 0.15)
rows = []
for i, d in enumerate(L.days[:-1]):
    if d < "2021-01-04" or d not in p314: continue
    e = L.expiry(d)
    if e is None or e > L.days[-1]: continue
    n = L.dte(d, e)
    if n not in (1, 2): continue
    at = L.atm(d, e)
    if at is None: continue
    S = at[1] + at[2]; sp = p314[d]; j = L.allidx.index(d); ch = L.idx.close.iloc[j] - L.idx.close.iloc[j - 5]; x = L.days[i + 1]
    era = "P1 2021-Aug25" if d <= "2025-08-29" else ("P2a Sep25-Jul26" if d < "2026-08-03" else "P2b Aug3+")
    for kc, kp, sh in itertools.product(KC, KP, SH):
        c = sp + sh * ch; ce = L.by_strike(d, e, "CE", c + kc * S); pe = L.by_strike(d, e, "PE", c - kp * S)
        a, b = val(x, e, "CE", ce[0]), val(x, e, "PE", pe[0])
        if a is None or b is None: continue
        rows.append(dict(era=era, kc=kc, kp=kp, sh=sh, net=ce[1] + pe[1] - a - b - 2))
R = pd.DataFrame(rows)
G = R.pivot_table(index=["kc", "kp", "sh"], columns="era", values="net", aggfunc="sum").round(0)
G["rank P1"] = G["P1 2021-Aug25"].rank(ascending=False).astype(int); G["rank P2a"] = G["P2a Sep25-Jul26"].rank(ascending=False).astype(int); G["rank P2b"] = G["P2b Aug3+"].rank(ascending=False).astype(int)
print(G.sort_values("P2a Sep25-Jul26", ascending=False).to_string())
