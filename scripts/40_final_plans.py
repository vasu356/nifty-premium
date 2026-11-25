"""Month-wise progress of complete weekly plans from Sep 2025 (realistic live-15:14 inputs), with 2021-Aug25 yearly sanity
check, weekly risk and an equity chart. Uses results/manual/final_grid_trades.csv.gz."""
import os, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(ROOT, "results", "manual")
pd.set_option("display.width", 270); pd.set_option("display.max_rows", 100)
T = pd.read_csv(os.path.join(R, "final_grid_trades.csv.gz"))
pick = lambda comp, var: T[(T.comp == comp) & (T["var"] == var)]
FRI = pick("FRI", "call 0.75 / put 1.0 / shift 0.15"); MON0 = pick("MON", "call 0.75 / put 1.0 / shift 0.15"); MON1 = pick("MON", "call 0.5 / put 1.0 / shift 0.15")
PW, PT, PU = pick("PUT WED", "put 2.5xS"), pick("PUT THU", "put 2.5xS"), pick("PUT TUE", "put 2.5xS")
PLANS = {"A original (Fri+Mon 0.75/1.0)": [FRI, MON0], "B Fri 0.75 + Mon call 0.5": [FRI, MON1],
         "C = B + far puts Wed,Thu": [FRI, MON1, PW, PT], "D = C + far put Tue": [FRI, MON1, PW, PT, PU]}
def plan(parts, lo, hi): t = pd.concat(parts); return t[(t.sell >= lo) & (t.sell <= hi)]
rows = []
for nm, parts in PLANS.items():
    for per, lo, hi in (("Sep25-now", "2025-09-01", "2099"), ("since 3 Aug 2026", "2026-08-03", "2099"), ("2021-Aug25", "2021-01-01", "2025-08-31")):
        t = plan(parts, lo, hi).sort_values("sell"); wk = t.groupby("expiry").net.sum(); mo = t.groupby(t.sell.str[:7]).net.sum(); eq = t.groupby("sell").net.sum().cumsum()
        rows.append(dict(plan=nm, period=per, trades=len(t), net=round(t.net.sum()), rupees=f"{t.net.sum()*65/1e5:.2f}L", worst_week=round(wk.min()),
                         worst_month=round(mo.min()), months_pos=f"{(mo>0).sum()}/{len(mo)}", max_dd=round((eq - eq.cummax()).min())))
print(pd.DataFrame(rows).to_string(index=False))
print("\n===== MONTH-WISE from Sep 2025 (net points by month of entry; cumulative in brackets)")
M = {}
for nm, parts in PLANS.items():
    t = plan(parts, "2025-09-01", "2099"); M[nm[:1]] = t.groupby(t.sell.str[:7]).net.sum()
M = pd.DataFrame(M).fillna(0)
comp = pd.DataFrame({"Fri": FRI[FRI.sell >= "2025-09-01"].groupby(FRI.sell.str[:7]).net.sum(), "Mon(0.5)": MON1[MON1.sell >= "2025-09-01"].groupby(MON1.sell.str[:7]).net.sum(),
                     "Put Wed": PW[PW.sell >= "2025-09-01"].groupby(PW.sell.str[:7]).net.sum(), "Put Thu": PT[PT.sell >= "2025-09-01"].groupby(PT.sell.str[:7]).net.sum(),
                     "Put Tue": PU[PU.sell >= "2025-09-01"].groupby(PU.sell.str[:7]).net.sum()}).fillna(0)
out = pd.concat([comp.round(0), M.round(0)], axis=1)
for c in "ABCD": out[c + " cum"] = M[c].cumsum().round(0)
out.loc["TOTAL"] = out.sum(numeric_only=True); out.loc["TOTAL", [c + " cum" for c in "ABCD"]] = np.nan
print(out.fillna("").to_string())
print("\n===== 2021-Aug 2025 yearly (sanity check)")
Y = {nm[:1]: plan(p, "2021-01-01", "2025-08-31").groupby(lambda i: None).size() for nm, p in PLANS.items()}
print(pd.DataFrame({nm[:1]: (lambda t: t.groupby(t.sell.str[:4]).net.sum())(plan(p, "2021-01-01", "2025-08-31")) for nm, p in PLANS.items()}).round(0).to_string())
print("\n===== worst 5 weeks of plan C since Sep 2025")
t = plan(PLANS["C = B + far puts Wed,Thu"], "2025-09-01", "2099"); w = t.groupby(["expiry", "comp"]).net.sum().unstack(fill_value=0); w["total"] = w.sum(axis=1)
print(w.nsmallest(5, "total").round(0).to_string())
fig, ax = plt.subplots(figsize=(11, 5))
for nm, parts in PLANS.items():
    t = plan(parts, "2025-09-01", "2099"); eq = t.groupby("sell").net.sum().cumsum(); eq.index = pd.to_datetime(eq.index); ax.plot(eq.index, eq.values, label=nm, lw=1.7)
ax.axvline(pd.Timestamp("2026-08-03"), color="grey", ls="--", lw=.8); ax.text(pd.Timestamp("2026-08-05"), ax.get_ylim()[0] + 50, "closing auction starts", fontsize=8, color="grey")
ax.set_title("Cumulative net points, 1 lot per position, Sep 2025 -> 23 Nov 2026 (strikes from live 3:14 PM Nifty)"); ax.grid(alpha=.3); ax.legend(fontsize=8, loc="upper left")
plt.tight_layout(); plt.savefig(os.path.join(ROOT, "results", "charts", "final_plans_equity.png"), dpi=130); print("chart saved")
