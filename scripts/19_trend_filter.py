"""Test 'only sell extra days when Nifty is not in a pullback' filters, year by year (net of 2 pts charges)."""
import os, numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "results", "manual")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
T = pd.read_csv(os.path.join(R, "extra_day_trades.csv.gz")); T["net"] = T.pnl - 2
F = pd.read_csv(os.path.join(R, "extra_day_features.csv")).drop(columns=["dte"])
D = T.merge(F, on="sell"); D["yr"] = D.sell.str[:4]; D["per"] = np.where(D.sell <= "2025-08-29", "P1", "P2")
FILT = {"none": lambda d: d.net == d.net,
        "close > 20d avg": lambda d: d.dist_ma20_p > 0,
        "close > 20d avg -0.5%": lambda d: d.dist_ma20_p > -0.5,
        "within 1% of 20d high": lambda d: d.dd_high20_p > -1,
        "within 2% of 20d high": lambda d: d.dd_high20_p > -2,
        "10d return > 0": lambda d: d.retn10p > 0,
        "close>20d avg AND 10d ret>0": lambda d: (d.dist_ma20_p > 0) & (d.retn10p > 0),
        "close>50d avg": lambda d: d.dist_ma50_p > 0}
def show(cfg, dtes, label):
    d = D[(D.cfg == cfg) & D.dte.isin(dtes)]
    rows = []
    for nm, f in FILT.items():
        s = d[f(d)]
        y = s.groupby("yr").net.sum()
        rows.append(dict(filter=nm, n=len(s), net=s.net.sum(), avg=s.net.mean(),
                         P1=s[s.per == "P1"].net.sum(), P2=s[s.per == "P2"].net.sum(),
                         n2=(s.per == "P2").sum(), **{k: y.get(k, 0) for k in ("2021", "2022", "2023", "2024", "2025", "2026")}))
    print(f"\n== {label}  cfg={cfg} dte={dtes}"); print(pd.DataFrame(rows).round(1).to_string(index=False))
for cfg in ("F0.75_1.0", "F1.0_1.0", "P30"):
    show(cfg, [3, 4, 5], "EXTRA DAYS Tue/Wed/Thu")
show("F0.75_1.0", [3], "Thursday only (dte3)"); show("F0.75_1.0", [4], "Wednesday only (dte4)")
show("F0.75_1.0", [1, 2], "BASE formula days (skip filter test)")
