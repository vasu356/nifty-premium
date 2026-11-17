"""Read the leg-level decay map: avg net points per short leg (credit - value - 1 point charge) by distance and holding days."""
import os, numpy as np, pandas as pd
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(ROOT, "results", "manual")
pd.set_option("display.width", 260); pd.set_option("display.max_rows", 400)
T = pd.read_csv(os.path.join(R, "decay_map_legs.csv.gz")); T["per"] = np.where(T.sell >= "2025-09-01", "P2", "P1")
NAME = {"P2": {3: "THU", 4: "WED", 5: "TUE"}, "P1": {3: "Mon", 4: "Fri", 5: "Thu"}}
def mat(per, dte, side, stat):
    x = T[(T.per == per) & (T.dte == dte) & (T.side == side)]
    out = {}
    for h in range(1, dte + 1):
        net = x.groupby("m").apply(lambda g: (g.credit - g[f"v{h}"] - 1))
        if stat == "avg": out[f"h{h}"] = x.assign(n=x.credit - x[f"v{h}"] - 1).groupby("m").n.mean()
        if stat == "win": out[f"h{h}"] = x.assign(n=x.credit - x[f"v{h}"] - 1).groupby("m").n.apply(lambda s: (s > 0).mean() * 100)
        if stat == "worst": out[f"h{h}"] = x.assign(n=x.credit - x[f"v{h}"] - 1).groupby("m").n.min()
    df = pd.DataFrame(out); df.insert(0, "credit", x.groupby("m").credit.mean()); return df
for dte in (3, 4, 5):
    for side in ("CE", "PE"):
        print(f"\n######## entry {NAME['P2'][dte]} (P2) / {NAME['P1'][dte]} (P1): {dte} days to expiry, SHORT {side}.  h1 = next close ... h{dte} = expiry")
        a = mat("P2", dte, side, "avg"); b = mat("P1", dte, side, "avg"); w = mat("P2", dte, side, "win"); wr = mat("P2", dte, side, "worst")
        a.columns = ["P2 credit"] + [f"P2 avg {c}" for c in a.columns[1:]]; b.columns = ["P1 credit"] + [f"P1 avg {c}" for c in b.columns[1:]]
        wexp = w.iloc[:, -1].rename("P2 win% exp"); wst = wr.iloc[:, -1].rename("P2 worst exp")
        print(pd.concat([a, wexp, wst, b], axis=1).round(1).to_string())
