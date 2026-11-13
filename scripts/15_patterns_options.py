"""Options-linked and intraday pattern study (see chat report).
B: implied vs realised, shape of overnight moves, strike breach rates.
C: hourly risk profile, 3:25 PM price vs official close.
"""
import sys, os, importlib
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 100)

L = labm.Lab(start="2020-11-15")
rows = []
for i, d in enumerate(L.days):
    if d < "2021-01-04" or i >= len(L.days) - 1:
        continue
    e = L.expiry(d)
    if e is None:
        continue
    n = L.dte(d, e)
    if n not in (1, 2):
        continue
    a = L.atm(d, e)
    if a is None:
        continue
    S = a[1] + a[2]; sp = L.spot[d]; x = L.days[i + 1]; mv = L.spot[x] - sp
    ex = [z for z in L.days[i + 1:] if z <= e]
    mv_e = L.spot[ex[-1]] - sp if ex and ex[-1] == e else np.nan
    j = L.allidx.index(d); tr = 0.15 * (sp - L.idx.close.iloc[j - 5]); c = sp + tr
    ce = L.by_strike(d, e, "CE", c + 0.75 * S); pe = L.by_strike(d, e, "PE", c - 1.0 * S)
    if ce is None or pe is None:
        continue
    rows.append(dict(d=d, n=n, S=S, sp=sp, mv=mv, mv_e=mv_e, ck=ce[0], pk=pe[0], sx=L.spot[x], yr=d[:4],
                     era="Tuesday era" if d >= "2025-09-01" else "Thursday era"))
t = pd.DataFrame(rows)
t["z"] = t.mv / t.S; t["abs"] = t.mv.abs()
t["call_breach"] = t.sx > t.ck; t["put_breach"] = t.sx < t.pk; t["either"] = t.call_breach | t.put_breach
t.to_csv(os.path.join(ROOT, "results", "manual", "pattern_trades.csv"), index=False, float_format="%.3f")

print("B1. IMPLIED vs REALISED: average actual |move| / straddle price (below 1.00 = market over-prices movement)")
for era, g in (("2021-Aug25", t[t.era == "Thursday era"]), ("Sep25-now", t[t.era == "Tuesday era"]), ("ALL", t)):
    for n, gg in g.groupby("n"):
        r = gg["abs"] / gg.S; re = (gg.mv_e.abs() / gg.S).dropna()
        print(f"   {era:11s} {'Monday-type (1 day)' if n == 1 else 'Friday-type (2 days)'}: trades {len(gg):3d} | avg straddle {gg.S.mean():6.1f} | avg next-night |move| {gg['abs'].mean():6.1f} | ratio next-night {r.mean():.2f} | ratio to expiry {re.mean():.2f}")
print("\nB2. SHAPE OF THE NEXT-NIGHT MOVE in straddle units (z = move / straddle)")
q = [0.05, 0.10, 0.25, 0.5, 0.75, 0.90, 0.95]
for n, g in t.groupby("n"):
    print(f"   {'Monday-type' if n == 1 else 'Friday-type'} z quantiles 5/10/25/50/75/90/95%:", [round(g.z.quantile(k), 2) for k in q],
          "| |z|>1:", round((g.z.abs() > 1).mean() * 100, 1), "% | up>0.75:", round((g.z > 0.75).mean() * 100, 1), "% | down<-1.0:", round((g.z < -1).mean() * 100, 1), "%")
print("\nB3. HOW OFTEN EACH STRIKE ENDS IN THE MONEY at buy-back (current formula strikes)")
for n, g in t.groupby("n"):
    print(f"   {'Monday-type' if n == 1 else 'Friday-type'}: call breached {g.call_breach.mean()*100:.1f}% | put breached {g.put_breach.mean()*100:.1f}% | either {g.either.mean()*100:.1f}% ({len(g)} trades)")
print("   share of trades with either strike breached, by year:", (t.groupby("yr").either.mean() * 100).round(1).to_dict())
b = t.reindex(t.z.abs().sort_values(ascending=False).index).head(20)
print("\nB4. 20 biggest overnight moves (straddle units): up", int((b.z > 0).sum()), "| down", int((b.z < 0).sum()), "| avg size up", round(b[b.z > 0].z.mean(), 2), "down", round(b[b.z < 0].z.mean(), 2))
print("   all nights: z>+0.75:", round((t.z > 0.75).mean() * 100, 1), "% | z<-0.75:", round((t.z < -0.75).mean() * 100, 1), "% | z>+1:", round((t.z > 1).mean() * 100, 1), "% | z<-1:", round((t.z < -1).mean() * 100, 1), "%")

h = pd.read_csv(os.path.join(ROOT, "data", "market", "nifty_1h.csv"), parse_dates=["ts"])
h["day"] = h.ts.dt.strftime("%Y-%m-%d"); h["hr"] = h.ts.dt.strftime("%H:%M")
dly = pd.read_csv(os.path.join(ROOT, "data", "market", "nifty_1d.csv"), parse_dates=["ts"])
dly["day"] = dly.ts.dt.strftime("%Y-%m-%d"); dly = dly.drop_duplicates("day").set_index("day")
h["ret"] = np.log(h.close / h.open) * 100
full = h.groupby("day").filter(lambda g: len(g) >= 7)
full = full[full.hr != "15:30"]
prev = dly.close.shift()
gap = (np.log(dly.open / prev) * 100).reindex(full.day.unique()).dropna()
prof = full.pivot_table(index="day", columns="hr", values="ret")
print(f"\nC1. WHEN DOES THE RISK HAPPEN? share of squared movement ({len(prof)} full sessions, Nov 2024 - Nov 2026)")
def share(days, label):
    p = prof.loc[prof.index.isin(days)]; gp = gap.reindex(p.index).dropna()
    comp = {"gap": (gp ** 2).sum()}; comp.update({c: (p[c].dropna() ** 2).sum() for c in p.columns})
    tot = sum(comp.values()); print(f"   {label:30s} ({len(p):3d} days): " + " | ".join(f"{k} {100*v/tot:.0f}%" for k, v in comp.items()))
alld = list(prof.index); wd = pd.to_datetime(pd.Series(alld)).dt.dayofweek.values
share(alld, "all days"); share([d for d, w in zip(alld, wd) if w == 0], "Mondays"); share([d for d, w in zip(alld, wd) if w == 4], "Fridays")
share([d for d in alld if d >= "2025-09-01" and pd.Timestamp(d).dayofweek == 1], "Tuesdays (expiry) Sep25+")
share([d for d in alld if d >= "2025-09-01" and pd.Timestamp(d).dayofweek != 1], "other days Sep25+")
m5 = pd.read_csv(os.path.join(ROOT, "data", "market", "nifty_5m.csv"), parse_dates=["ts"])
m5["day"] = m5.ts.dt.strftime("%Y-%m-%d"); m5["hm"] = m5.ts.dt.strftime("%H:%M")
p = m5.pivot_table(index="day", columns="hm", values="close", aggfunc="last")
dd = pd.DataFrame({"p1525": p["15:25"], "p1500": p["15:00"], "close": dly.close.reindex(p.index)}).dropna()
d1 = dd.p1525 - dd.close; d2 = dd.close - dd.p1500
print(f"\nC2. NIFTY at 3:25 PM vs OFFICIAL CLOSE ({len(dd)} sessions): |diff| median {d1.abs().median():.1f}, mean {d1.abs().mean():.1f}, p90 {d1.abs().quantile(.9):.1f}, max {d1.abs().max():.1f} pts; 3:00 PM -> close avg |{d2.abs().mean():.1f}| pts")
