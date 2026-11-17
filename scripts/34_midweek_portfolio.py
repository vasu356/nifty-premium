"""Add far-OTM put selling on Tue/Wed/Thu (held to expiry) to the Fri/Mon formula; weekly risk and equity curves."""
import os, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(ROOT, "results", "manual"); C = os.path.join(ROOT, "results", "charts")
pd.set_option("display.width", 260); pd.set_option("display.max_rows", 100)
ET = pd.read_csv(os.path.join(R, "extra_day_trades.csv.gz")); EF = pd.read_csv(os.path.join(R, "extra_day_features.csv"))[["sell", "exit", "expiry"]]
F = ET[(ET.cfg == "F0.75_1.0") & ET.dte.isin([1, 2])].merge(EF, on="sell")
F = F.assign(net=F.pnl - 2, piece="formula Fri+Mon")[["sell", "exit", "expiry", "net", "piece"]]
T = pd.read_csv(os.path.join(R, "decay_map_legs.csv.gz"))
T["vexp"] = T.apply(lambda r: r[f"v{int(r.dte)}"], axis=1); T["net"] = T.credit - T.vexp - 1; T["exit"] = T.expiry
DAYN = {3: "Thu", 4: "Wed", 5: "Tue"}
def legs(side, m, dtes):
    x = T[(T.side == side) & (T.m == m) & T.dte.isin(dtes)]
    return x.assign(piece=f"{side} {m}xS " + "+".join(DAYN[d] for d in sorted(dtes, reverse=True)))[["sell", "exit", "expiry", "net", "piece"]]
PLANS = {
 "A current (Fri+Mon formula)": [F],
 "B A + put 2.5xS on Tue,Wed,Thu": [F, legs("PE", 2.5, [3, 4, 5])],
 "C A + put 2.0xS on Tue,Wed,Thu": [F, legs("PE", 2.0, [3, 4, 5])],
 "D A + put 2.5xS on Wed,Thu": [F, legs("PE", 2.5, [3, 4])],
 "E A + put 2.5xS & call 3xS on Tue,Wed,Thu": [F, legs("PE", 2.5, [3, 4, 5]), legs("CE", 3.0, [3, 4, 5])],
 "F only puts 2.5xS Tue,Wed,Thu (no formula)": [legs("PE", 2.5, [3, 4, 5])],
}
def stats(t, lo, hi):
    t = t[(t.sell >= lo) & (t.sell <= hi)].sort_values("exit")
    eq = t.groupby("exit").net.sum().cumsum(); wk = t.groupby("expiry").net.sum(); mo = t.groupby(t.exit.str[:7]).net.sum()
    return dict(trades=len(t), net=round(t.net.sum()), rupees=round(t.net.sum() * 65), worst_week=round(wk.min()), weeks_neg=f"{(wk < 0).sum()}/{len(wk)}",
                max_dd=round((eq - eq.cummax()).min()), worst_month=round(mo.min()), months_pos=f"{(mo > 0).sum()}/{len(mo)}")
curves = {}
for per, lo, hi in (("Sep 2025 -> now", "2025-09-01", "2099"), ("2021 -> Aug 2025", "2021-01-01", "2025-08-31")):
    rows = []
    for nm, parts in PLANS.items():
        t = pd.concat(parts); rows.append(dict(plan=nm, **stats(t, lo, hi)))
    print(f"\n===== {per}"); print(pd.DataFrame(rows).to_string(index=False))
print("\n===== yearly net points")
yr = {nm: pd.concat(p).groupby(lambda i: None).size() for nm, p in PLANS.items()}
Y = pd.DataFrame({nm[:1]: pd.concat(p).groupby(pd.concat(p).exit.str[:4]).net.sum() for nm, p in PLANS.items()}).round(0); print(Y.to_string())
print("\n===== Sep 2025 -> now: monthly net points")
M = pd.DataFrame({nm[:1]: (lambda t: t[t.sell >= "2025-09-01"].groupby(t[t.sell >= "2025-09-01"].exit.str[:7]).net.sum())(pd.concat(p)) for nm, p in PLANS.items()}).round(0).fillna(0).astype(int); print(M.to_string())
print("\n===== worst 6 weeks of plan B (all years)")
t = pd.concat(PLANS["B A + put 2.5xS on Tue,Wed,Thu"]); wk = t.groupby(["expiry", "piece"]).net.sum().unstack(fill_value=0); wk["total"] = wk.sum(axis=1); print(wk.nsmallest(6, "total").round(0).to_string())
fig, axes = plt.subplots(2, 1, figsize=(11, 9))
for ax, (lo, title) in zip(axes, (("2025-09-01", "Sep 2025 -> Nov 2026 (Tuesday expiry)"), ("2021-01-01", "Jan 2021 -> Nov 2026"))):
    for nm in ("A current (Fri+Mon formula)", "B A + put 2.5xS on Tue,Wed,Thu", "C A + put 2.0xS on Tue,Wed,Thu", "E A + put 2.5xS & call 3xS on Tue,Wed,Thu", "F only puts 2.5xS Tue,Wed,Thu (no formula)"):
        t = pd.concat(PLANS[nm]); t = t[t.sell >= lo]; eq = t.groupby("exit").net.sum().cumsum(); eq.index = pd.to_datetime(eq.index)
        ax.plot(eq.index, eq.values, label=nm, lw=1.6)
    ax.set_title(f"Cumulative net points, 1 lot per position — {title}"); ax.grid(alpha=.3); ax.axhline(0, color="k", lw=.6); ax.legend(fontsize=8, loc="upper left")
plt.tight_layout(); plt.savefig(os.path.join(C, "midweek_put_equity.png"), dpi=130); print("chart saved")
