"""Analyse the expiry-day option BUYING test (see 29_buy_after_expiry.py)."""
import os, numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(ROOT, "results", "manual")
pd.set_option("display.width", 260); pd.set_option("display.max_rows", 300)
T = pd.read_csv(os.path.join(R, "buy_trades.csv.gz"))
T["per"] = np.where(T.sell >= "2025-09-01", "P2", "P1")
key = ["sell", "per", "ek", "mode", "val", "expiry", "spot", "S", "mv_open", "mv_wc", "mv_tc"]
ce = T[T.opt == "CE"].set_index(key); pe = T[T.opt == "PE"].set_index(key)
both = ce[["cost", "wo", "wc", "tc", "wo_fb"]].add(pe[["cost", "wo", "wc", "tc", "wo_fb"]], fill_value=np.nan).dropna(subset=["cost"]).reset_index()
both["struct"] = "call+put"; both["legs"] = 2
c1 = ce[["cost", "wo", "wc", "tc", "wo_fb"]].reset_index().assign(struct="call only", legs=1)
p1 = pe[["cost", "wo", "wc", "tc", "wo_fb"]].reset_index().assign(struct="put only", legs=1)
A = pd.concat([both, c1, p1], ignore_index=True)
for x in ("wo", "wc", "tc"):
    A[x + "_net"] = A[x] - A.legs
A.to_csv(os.path.join(R, "buy_structs.csv.gz"), index=False, float_format="%.3f")
def lab(r):
    if r["mode"] == "S":
        v = r["val"]
        return "ATM" if v == 0 else (f"ITM {-v:g}xS" if v < 0 else f"OTM {v:g}xS")
    return f"prem Rs{int(r['val'])}"
A["strike"] = A.apply(lab, axis=1)
order = ["ITM 0.5xS", "ITM 0.25xS", "ATM", "OTM 0.25xS", "OTM 0.5xS", "OTM 0.75xS", "OTM 1xS", "OTM 1.5xS", "prem Rs150", "prem Rs100", "prem Rs75", "prem Rs50", "prem Rs30", "prem Rs20", "prem Rs10"]
def table(per, ek, struct):
    x = A[(A.per == per) & (A.ek == ek) & (A.struct == struct)]
    g = x.groupby("strike").agg(n=("cost", "size"), cost=("cost", "mean"),
        wo_tot=("wo_net", "sum"), wo_avg=("wo_net", "mean"), wo_win=("wo_net", lambda s: (s > 0).mean() * 100),
        wc_tot=("wc_net", "sum"), wc_avg=("wc_net", "mean"), wc_win=("wc_net", lambda s: (s > 0).mean() * 100), wc_best=("wc_net", "max"), wc_worst=("wc_net", "min"),
        tc_tot=("tc_net", "sum"), tc_win=("tc_net", lambda s: (s > 0).mean() * 100), open_fallback=("wo_fb", "sum"))
    return g.reindex([o for o in order if o in g.index])
for per in ("P2", "P1"):
    for ek in (0, 1):
        for st in ("call+put", "call only", "put only"):
            print(f"\n##### {per} ({'Sep 2025-now, buy Tue' if per=='P2' else '2021-Aug 2025, buy Thu'})  expiry={'next week' if ek==0 else 'week after'}  {st}   [points net of 1/leg]")
            print(table(per, ek, st).round(1).to_string())
