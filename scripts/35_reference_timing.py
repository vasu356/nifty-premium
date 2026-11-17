"""Which Nifty reading to use when choosing strikes. Compares the official close (used by the backtest), the options-implied
Nifty (ATM strike + call - put) and the live Nifty at 15:00-15:28 from 1-minute data, before and after the closing auction
session (3 Aug 2026). Fri/Mon formula (net of 2 pts) and Wed/Thu far put 2.5xS (net of 1 pt), from Sep 2025."""
import sys, os, importlib, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab"); L = labm.Lab(start="2025-06-01")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
m = pd.read_csv(os.path.join(ROOT, "data", "market_user", "nifty50_1min.csv")); m = m[m.datetime >= "2025-06-01"]
m["date"] = m.datetime.str[:10]; m["t"] = m.datetime.str[11:16]
piv = m.pivot_table(index="date", columns="t", values="close", aggfunc="last")
def val(x, e, o, k):
    if x == e: s = L.spot[x]; return max(0, s - k) if o == "CE" else max(0, k - s)
    q = L.q(x, e, o, k); return None if q is None else q["close"]
rows = []
for i, d in enumerate(L.days[:-1]):
    if d < "2025-09-01" or d not in piv.index: continue
    e = L.expiry(d)
    if e is None or e > L.days[-1]: continue
    n = L.dte(d, e); at = L.atm(d, e)
    if at is None or n > 4: continue
    S = at[1] + at[2]; j = L.allidx.index(d); tr = 0.15 * (L.idx.close.iloc[j] - L.idx.close.iloc[j - 5])
    refs = {"official close": L.spot[d], "options-implied": at[0] + at[1] - at[2]}
    for t in ("15:00", "15:10", "15:14", "15:20", "15:25"):
        if t in piv.columns and not pd.isna(piv.loc[d, t]): refs[f"Nifty {t}"] = piv.loc[d, t]
    for ref, sp in refs.items():
        if n in (1, 2):
            ce = L.by_strike(d, e, "CE", sp + tr + 0.75 * S); pe = L.by_strike(d, e, "PE", sp + tr - 1.0 * S); x = L.days[i + 1]
            a, b = val(x, e, "CE", ce[0]), val(x, e, "PE", pe[0])
            if a is not None and b is not None: rows.append(dict(d=d, kind="Fri/Mon formula", ref=ref, net=ce[1] + pe[1] - a - b - 2))
        if n in (3, 4):
            pe = L.by_strike(d, e, "PE", sp - 2.5 * S); rows.append(dict(d=d, kind="Wed/Thu far put", ref=ref, net=pe[1] - val(e, e, "PE", pe[0]) - 1))
R = pd.DataFrame(rows); R["era"] = np.where(R.d >= "2026-08-03", "Aug3+ (auction close)", "Sep25-Jul26")
print(R.pivot_table(index="ref", columns=["kind", "era"], values="net", aggfunc="sum").round(0).to_string())
