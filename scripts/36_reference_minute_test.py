"""Which Nifty value should be used to pick strikes? Every candidate reading, three eras:
  P1  = Jan 2021 - Aug 2025 (Thursday expiry, VWAP-based closes)
  P2a = Sep 2025 - 31 Jul 2026 (Tuesday expiry, VWAP-based closes)
  P2b = 3 Aug 2026 - 13 Nov 2026 (closing auction; live index stops 15:14)
Trades: Fri/Mon formula (call c+0.75S, put c-1.0S, c = ref + 0.15*5d change, net of 2 pts) and the far put
(ref - 2.5S, Wed/Thu entries i.e. dte 3-4, held to expiry, net of 1 pt). Option prices are NSE closing prices (30-min VWAP)."""
import sys, os, importlib, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab"); L = labm.Lab(start="2020-11-15")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "results", "manual")
pd.set_option("display.width", 260); pd.set_option("display.max_rows", 200)
m = pd.read_csv(os.path.join(ROOT, "data", "market_user", "nifty50_1min.csv")); m["date"] = m.datetime.str[:10]; m["t"] = m.datetime.str[11:16]
m = m[m.t >= "14:30"]; piv = m.pivot_table(index="date", columns="t", values="close", aggfunc="last")
twap = m[(m.t >= "15:00") & (m.t <= "15:14")].groupby("date").close.mean()
TIMES = ["14:30", "14:45", "15:00", "15:05", "15:10", "15:12", "15:14", "15:20", "15:25", "15:29"]
def settle_day(e):
    return max(x for x in L.days if x <= e)
def val(x, e, o, k):
    if x == settle_day(e): s = L.spot[x]; return max(0, s - k) if o == "CE" else max(0, k - s)
    q = L.q(x, e, o, k); return None if q is None else q["close"]
syn_gap = {}
rows, gap = [], []
for i, d in enumerate(L.days[:-1]):
    if d < "2021-01-04" or d not in piv.index: continue
    e = L.expiry(d)
    if e is None or e > L.days[-1]: continue
    n = L.dte(d, e); at = L.atm(d, e)
    if at is None: continue
    S = at[1] + at[2]; syn = at[0] + at[1] - at[2]; off = L.spot[d]
    syn_gap[d] = syn - off
    hist = [v for k, v in syn_gap.items() if k < d][-60:]
    carry = np.median(hist) if len(hist) >= 20 else np.nan
    if n > 4: continue
    j = L.allidx.index(d); tr = 0.15 * (L.idx.close.iloc[j] - L.idx.close.iloc[j - 5])
    refs = {"official close": off, "options-implied": syn, "options-implied minus carry": syn - carry if carry == carry else np.nan, "avg 15:00-15:14": twap.get(d, np.nan)}
    for t in TIMES:
        if t in piv.columns: refs[f"live {t}"] = piv.loc[d, t]
    era = "P1" if d <= "2025-08-29" else ("P2a" if d < "2026-08-03" else "P2b")
    gap.append({"era": era, **{k: v - off for k, v in refs.items()}})
    for ref, sp in refs.items():
        if sp != sp: continue
        if n in (1, 2):
            ce = L.by_strike(d, e, "CE", sp + tr + 0.75 * S); pe = L.by_strike(d, e, "PE", sp + tr - 1.0 * S); x = L.days[i + 1]
            a, b = val(x, e, "CE", ce[0]), val(x, e, "PE", pe[0])
            if a is not None and b is not None:
                rows.append(dict(d=d, era=era, kind="formula", dte=n, ref=ref, net=ce[1] + pe[1] - a - b - 2, credit=ce[1] + pe[1]))
        if n in (3, 4):
            pe = L.by_strike(d, e, "PE", sp - 2.5 * S)
            rows.append(dict(d=d, era=era, kind="far put", dte=n, ref=ref, net=pe[1] - val(settle_day(e), e, "PE", pe[0]) - 1, credit=pe[1]))
R = pd.DataFrame(rows); R.to_csv(os.path.join(OUT, "reference_minute_test.csv.gz"), index=False, float_format="%.3f")
order = ["live 14:30", "live 14:45", "live 15:00", "live 15:05", "live 15:10", "live 15:12", "live 15:14", "avg 15:00-15:14", "live 15:20", "live 15:25", "live 15:29",
         "official close", "options-implied", "options-implied minus carry"]
for kind in ("formula", "far put"):
    t = R[R.kind == kind].pivot_table(index="ref", columns="era", values="net", aggfunc=["sum", "count"])
    t.columns = [f"{a}_{b}" for a, b in t.columns]; t = t.reindex(order)
    t["avg/trade P2b"] = t["sum_P2b"] / t["count_P2b"]
    print(f"\n===== {kind}: total net points by Nifty reading used ({'Fri/Mon' if kind=='formula' else 'Wed/Thu far put 2.5xS'})"); print(t.round(1).to_string())
G = pd.DataFrame(gap)
print("\n===== average distance |reading - official close| in points")
print(G.groupby("era").agg(lambda s: s.abs().mean()).T.reindex(order).round(1).to_string())
