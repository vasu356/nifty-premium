"""Walk-forward ML: predict return-on-premium of an overnight strangle from end-of-day features, trade only when
the prediction is above a threshold. Models are retrained every half-year on strictly earlier data (labels end before the
test block starts). Pooled over dte 1..5 (dte is a feature). Test blocks: 2023-01 onward (P1 tail + P2).
Net = points - 2 charges."""
import os, sys, warnings, numpy as np, pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "results", "manual")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
CFG = os.environ.get("CFG", "F0.75_1.0")
T = pd.read_csv(os.path.join(R, "extra_day_trades.csv.gz")); T["net"] = T.pnl - 2
F = pd.read_csv(os.path.join(R, "extra_day_features.csv")).drop(columns=["dte"])
D = T[T.cfg == CFG].merge(F, on="sell").sort_values("sell").reset_index(drop=True)
D["dte"] = D.dte; D["y"] = D.net / D.credit
for w in (5, 10, 20, 60): D[f"vrp{w}"] = D.imp_day_p / D[f"rv{w}"]
D["vrp_rng5"] = D.imp_day_p / D.rng5
FEATS = [c for c in D.columns if c not in ("sell", "exit", "expiry", "cfg", "ce_k", "pe_k", "credit", "pnl", "ce_pnl", "pe_pnl", "net", "y", "spot", "move", "atm", "S", "dow")] + ["dow"]
FEATS = list(dict.fromkeys(FEATS))
BLOCKS = [("2022-07-01", "2023-01-01"), ("2023-01-01", "2023-07-01"), ("2023-07-01", "2024-01-01"), ("2024-01-01", "2024-07-01"), ("2024-07-01", "2025-01-01"),
          ("2025-01-01", "2025-07-01"), ("2025-07-01", "2026-01-01"), ("2026-01-01", "2027-01-01")]
BLOCKS = BLOCKS[1:]
MODELS = {"GBM": lambda: GradientBoostingRegressor(n_estimators=120, max_depth=2, learning_rate=0.04, subsample=0.7, min_samples_leaf=40, random_state=0),
          "Ridge": lambda: make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), RidgeCV(alphas=np.logspace(0, 4, 12)))}
X = D[FEATS]
preds = {m: pd.Series(np.nan, index=D.index) for m in MODELS}
for a, b in BLOCKS:
    tr = D.index[D.exit.lt(a)]; te = D.index[(D.sell >= a) & (D.sell < b)]
    ok = D.loc[tr, "y"].notna()
    for m, mk in MODELS.items():
        mdl = mk()
        Xtr = X.loc[tr[ok]]
        if m == "GBM": Xtr = Xtr.fillna(Xtr.median()); Xte = X.loc[te].fillna(Xtr.median())
        else: Xte = X.loc[te]
        mdl.fit(Xtr, D.loc[tr[ok], "y"].clip(-1.5, 1.0))
        preds[m].loc[te] = mdl.predict(Xte)
for m in MODELS: D["p_" + m] = preds[m]
O = D[D.sell >= BLOCKS[0][0]].copy(); O["yr"] = O.sell.str[:4]
def rep(sub, label):
    rows = []
    for nm, mask in label.items():
        s = sub[mask(sub)]
        y = s.groupby("yr").net.sum()
        rows.append(dict(rule=nm, n=len(s), net=s.net.sum(), avg=s.net.mean() if len(s) else np.nan, win=(s.net > 0).mean() * 100 if len(s) else np.nan,
                         **{k: round(y.get(k, 0), 0) for k in ("2023", "2024", "2025", "2026")}))
    print(pd.DataFrame(rows).round(1).to_string(index=False))
ex = O[O.dte.isin([3, 4, 5])]; base = O[O.dte.isin([1, 2])]
rules = {"always trade": lambda d: d.net == d.net}
for m in MODELS:
    for th in (0.0, 0.03, 0.06, 0.1):
        rules[f"{m} pred > {th}"] = (lambda m, th: lambda d: d["p_" + m] > th)(m, th)
rules["trend rule: >20d avg & 10d ret>0"] = lambda d: (d.dist_ma20_p > 0) & (d.retn10p > 0)
print("OUT-OF-SAMPLE (2023-01 onward) — EXTRA DAYS Tue/Wed/Thu (dte 3-5), cfg", CFG); rep(ex, rules)
for dt in (3, 4, 5):
    print(f"\n  dte {dt}"); rep(ex[ex.dte == dt], {k: v for k, v in rules.items() if k in ("always trade", "GBM pred > 0.0", "Ridge pred > 0.0", "GBM pred > 0.03", "Ridge pred > 0.03", "trend rule: >20d avg & 10d ret>0")})
print("\nBASE days (Fri/Mon, dte 1-2): does a model help SKIP bad ones?"); rep(base, {k: v for k, v in rules.items() if "trend" not in k})
# correlation of prediction with outcome
for m in MODELS: print(m, "OOS spearman(pred,y) extra:", round(ex[["p_" + m, "y"]].corr(method="spearman").iloc[0, 1], 3), " base:", round(base[["p_" + m, "y"]].corr(method="spearman").iloc[0, 1], 3))
O.to_csv(os.path.join(R, "wf_predictions.csv"), index=False, float_format="%.4f")
