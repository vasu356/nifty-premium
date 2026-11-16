"""Two signals found for the Fri/Mon formula trades (dte 1-2). Net = points - 2 charges.
A) richness ratio r = (ATM straddle / sqrt(dte) / spot, %) / (India VIX/sqrt(252)*0.8):
   high r (>= ~1.0) -> higher return per rupee of premium (28% vs 17% kept), same sign in 2021-25 and 2025-26, within Fri and Mon.
   Used only as a size tilt (see results/manual/ratio_signal_formula_days.csv).
B) last-hour lean: centre = spot + 0.15*5d change + s * (last-hour return, 14:25 -> close, in points); s in {0,1,2,3}
   (results/manual/lasthour_lean.csv, paired weekly-block bootstrap of the gain)."""
import os, sys, importlib, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(ROOT, "results", "manual")
L = labm.Lab(start="2020-11-15")
FD = pd.read_csv(os.path.join(R, "range_daily.csv"), index_col=0)
EF = pd.read_csv(os.path.join(R, "extra_day_features.csv")); EF = EF[EF.dte.isin([1, 2])]
# A) ratio buckets
ET = pd.read_csv(os.path.join(R, "extra_day_trades.csv.gz")); ET = ET[(ET.cfg == "F0.75_1.0") & ET.dte.isin([1, 2])]
D = ET.merge(EF[["sell", "imp_day_p"]], on="sell").merge(FD[["f_vix"]], left_on="sell", right_index=True)
D["net"] = D.pnl - 2; D["r"] = D.imp_day_p / D.f_vix; D["per"] = np.where(D.sell <= "2025-08-29", "P1", "P2")
D["bucket"] = pd.cut(D.r, [0, 0.85, 1.0, 9], labels=["<0.85", "0.85-1.0", ">=1.0"]).astype(str)
print(D.groupby(["per", "bucket"]).agg(n=("net", "size"), credit=("credit", "mean"), avg=("net", "mean")).round(1))
D.to_csv(os.path.join(R, "ratio_signal_formula_days.csv"), index=False, float_format="%.3f")
# B) last-hour lean
rows = []
for r in EF.itertuples():
    d = r.sell
    if d not in FD.index or pd.isna(FD.lasthr_ret.get(d)): continue
    sp = L.spot[d]; i = L.pos[d]; e = L.expiry(d); j = L.allidx.index(d)
    tr5 = 0.15 * (L.idx.close.iloc[j] - L.idx.close.iloc[j - 5]); lh = FD.lasthr_ret[d] / 100 * sp; x = L.days[i + 1]; o = {"sell": d, "exp": r.expiry}; ok = True
    for s in (0, 1.0, 2.0, 3.0):
        c = sp + tr5 + s * lh; ce = L.by_strike(d, e, "CE", c + 0.75 * r.S); pe = L.by_strike(d, e, "PE", c - 1.0 * r.S)
        qc, qp = (L.q(x, e, "CE", ce[0]), L.q(x, e, "PE", pe[0])) if ce and pe else (None, None)
        if qc is None or qp is None: ok = False; break
        o[f"s{s}"] = ce[1] + pe[1] - qc["close"] - qp["close"] - 2
    if ok: rows.append(o)
T = pd.DataFrame(rows); T["per"] = np.where(T.sell <= "2025-08-29", "P1", "P2")
print(T[["s0", "s1.0", "s2.0", "s3.0"]].sum().round(0)); T.to_csv(os.path.join(R, "lasthour_lean.csv"), index=False, float_format="%.2f")
