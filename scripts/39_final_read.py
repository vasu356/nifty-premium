"""Read the final grid: per component and variant -> 2021-Aug25 (P1), Sep25-Feb26 (H1), Mar26-now (H2), month-wise P2."""
import os, numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(ROOT, "results", "manual")
pd.set_option("display.width", 270); pd.set_option("display.max_rows", 300)
T = pd.read_csv(os.path.join(R, "final_grid_trades.csv.gz"))
T["per"] = np.where(T.sell <= "2025-08-29", "P1", np.where(T.sell <= "2026-02-28", "H1", "H2"))
def summ(g):
    p2 = g[g.per != "P1"].sort_values("sell"); eq = p2.net.cumsum(); mo = p2.groupby(p2.sell.str[:7]).net.sum()
    return pd.Series(dict(P1=g[g.per == "P1"].net.sum(), P1_avg=g[g.per == "P1"].net.mean(), H1=g[g.per == "H1"].net.sum(), H2=g[g.per == "H2"].net.sum(),
        P2=p2.net.sum(), n2=len(p2), avg2=p2.net.mean(), win2=(p2.net > 0).mean() * 100, worst2=p2.net.min(), dd2=(eq - eq.cummax()).min(),
        mpos=f"{(mo > 0).sum()}/{len(mo)}", credit2=p2.credit.mean()))
S = T.groupby(["comp", "var"]).apply(summ).reset_index()
for c in ("P1", "H1", "H2"):
    S["r" + c] = S.groupby("comp")[c].rank(ascending=False)
S["worst_rank"] = S[["rP1", "rH1", "rH2"]].max(axis=1)
S.to_csv(os.path.join(R, "final_grid_summary.csv"), index=False, float_format="%.2f")
CUR = {"FRI": "call 0.75 / put 1.0 / shift 0.15", "MON": "call 0.75 / put 1.0 / shift 0.15"}
for comp in ("FRI", "MON"):
    x = S[S.comp == comp]
    print(f"\n######## {comp}: {x.shape[0]} variants. Current = {CUR[comp]}")
    cols = ["var", "P1", "H1", "H2", "P2", "avg2", "win2", "worst2", "dd2", "mpos", "credit2", "rP1", "rH1", "rH2", "worst_rank"]
    print("-- current:"); print(x[x["var"] == CUR[comp]][cols].round(1).to_string(index=False))
    print("-- most robust (best worst-rank across P1/H1/H2):"); print(x.nsmallest(8, ["worst_rank", "rH2"])[cols].round(1).to_string(index=False))
    print("-- top 5 by P2 total:"); print(x.nlargest(5, "P2")[cols].round(1).to_string(index=False))
    # selection test: pick best on H1 -> its H2
    b = x.loc[x.H1.idxmax()]; print(f"-- best on H1 = {b['var']}: H1 {b.H1:.0f} -> H2 {b.H2:.0f}  (current H2 {x[x['var']==CUR[comp]].H2.iloc[0]:.0f}; median H2 {x.H2.median():.0f})")
for comp in sorted(c for c in S.comp.unique() if c.startswith(("PUT", "CALL"))):
    x = S[S.comp == comp]; print(f"\n######## {comp}"); print(x[["var", "P1", "P1_avg", "H1", "H2", "P2", "avg2", "win2", "worst2", "dd2", "mpos", "credit2"]].round(1).to_string(index=False))
