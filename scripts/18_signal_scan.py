"""Univariate scan: which end-of-day features separate good from bad extra-day (dte 3-5) trades?
Quantile cut-offs come from P1 only; P2 (Sep 2025+) is untouched out-of-sample. Net = points - 2 charges."""
import os, numpy as np, pandas as pd
from scipy import stats
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "results", "manual")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
T = pd.read_csv(os.path.join(R, "extra_day_trades.csv.gz")); T["net"] = T.pnl - 2
F = pd.read_csv(os.path.join(R, "extra_day_features.csv"))
TARGET = os.environ.get("TARGET", "net")
CFG = os.environ.get("CFG", "F0.75_1.0"); DTES = [int(x) for x in os.environ.get("DTES", "3,4,5").split(",")]
D = T[(T.cfg == CFG) & T.dte.isin(DTES)].merge(F.drop(columns=["dte"]), on="sell")
D["per"] = np.where(D.sell <= "2025-08-29", "P1", "P2")
D["retn"] = D.net / D.credit
for w in (5, 10, 20, 60):
    D[f"vrp{w}"] = D.imp_day_p / D[f"rv{w}"]
D["vrp_rng5"] = D.imp_day_p / D.rng5
D["vrp_vix"] = D.imp_day_p / (D.vix / np.sqrt(252) * 0.8)   # implied option move vs India VIX-implied daily move
feats = ["vrp5","vrp10","vrp20","vrp60","vrp_rng5","vrp_vix"] + [c for c in F.columns if c not in ("sell", "exit", "expiry", "dte", "spot", "move", "atm", "S")] + ["dte"]
D["dte"] = D.dte
p1, p2 = D[D.per == "P1"], D[D.per == "P2"]
print(f"{CFG} dte {DTES}: P1 n={len(p1)} net={p1.net.sum():.0f} avg={p1.net.mean():.2f} | P2 n={len(p2)} net={p2.net.sum():.0f} avg={p2.net.mean():.2f}")
rows = []
for f in feats:
    a, b = p1[[f, TARGET]].dropna(), p2[[f, TARGET]].dropna()
    if a[f].nunique() < 4 or len(b) < 30:
        continue
    r1, pv1 = stats.spearmanr(a[f], a[TARGET]); r2, pv2 = stats.spearmanr(b[f], b[TARGET])
    q = np.unique(np.quantile(a[f], [1/3, 2/3]))
    bins = lambda x: np.digitize(x[f], q)
    g1 = a.groupby(bins(a))[TARGET].agg(["mean", "size"]); g2 = b.groupby(bins(b))[TARGET].agg(["mean", "size"])
    rows.append(dict(feat=f, rho1=r1, p1=pv1, rho2=r2, p2=pv2, same_sign=np.sign(r1) == np.sign(r2),
                     lo1=g1["mean"].get(0, np.nan), mid1=g1["mean"].get(1, np.nan), hi1=g1["mean"].get(2, np.nan),
                     lo2=g2["mean"].get(0, np.nan), mid2=g2["mean"].get(1, np.nan), hi2=g2["mean"].get(2, np.nan)))
S = pd.DataFrame(rows).sort_values("p1")
print(S.round(3).to_string(index=False))
