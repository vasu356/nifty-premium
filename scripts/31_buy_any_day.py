"""Long ATM straddle / 0.5S strangle bought at ANY day's close on the first expiry >= 5 trading days away,
sold at next open, next close, or the close 2 trading days later. Net of 1 point per leg. Both eras, by weekday."""
import os, sys, importlib, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = os.path.join(ROOT, "results", "manual")
pd.set_option("display.width", 250)
L = labm.Lab(start="2020-11-15")
rows = []
for i, d in enumerate(L.days[:-2]):
    if d < "2021-01-04": continue
    es = [e for e in L.exps[d] if e > d and L.dte(d, e) >= 5]
    if not es: continue
    e = es[0]; at = L.atm(d, e)
    if at is None: continue
    sp = L.spot[d]; S = at[1] + at[2]; x1, x2 = L.days[i + 1], L.days[i + 2]
    for nm, legs in (("ATM straddle", [("CE", at[0], at[1]), ("PE", at[0], at[2])]),
                     ("strangle 0.5S", [("CE",) + tuple(L.by_strike(d, e, "CE", sp + 0.5 * S) or (None, None)), ("PE",) + tuple(L.by_strike(d, e, "PE", sp - 0.5 * S) or (None, None))])):
        if any(k is None for _, k, _ in legs): continue
        cost = sum(c for _, _, c in legs); out = dict(sell=d, wd=pd.Timestamp(d).day_name()[:3], struct=nm, dte=L.dte(d, e), cost=cost, nights=(pd.Timestamp(x1) - pd.Timestamp(d)).days)
        ok = True
        for lab, x, f in (("next_open", x1, "open"), ("next_close", x1, "close"), ("close_2d", x2, "close")):
            v = 0
            for o, k, c in legs:
                q = L.q(x, e, o, k)
                if q is None: ok = False; break
                v += q["open"] if (f == "open" and q["open"] > 0) else q["close"]
            out[lab] = v - cost - 2
        if ok: rows.append(out)
T = pd.DataFrame(rows); T["per"] = np.where(T.sell >= "2025-09-01", "Sep25+ (Tue expiry)", "2021-Aug25 (Thu expiry)")
T.to_csv(os.path.join(OUT, "buy_any_day.csv.gz"), index=False, float_format="%.3f")
for st in ("ATM straddle", "strangle 0.5S"):
    x = T[T.struct == st]
    g = x.groupby(["per", "wd"]).agg(n=("cost", "size"), dte=("dte", "median"), cost=("cost", "mean"), next_open=("next_open", "mean"), next_close=("next_close", "mean"),
                                      win_close=("next_close", lambda s: (s > 0).mean() * 100), close_2d=("close_2d", "mean"), tot_close=("next_close", "sum"), tot_2d=("close_2d", "sum"))
    g = g.reindex([(p, w) for p in x.per.unique() for w in ("Mon", "Tue", "Wed", "Thu", "Fri")]).dropna(how="all")
    print(f"\n==== LONG {st} (avg points per trade, net)\n", g.round(1).to_string())
