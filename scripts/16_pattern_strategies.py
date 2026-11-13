"""Strategy tests driven by the pattern study.
D1: exit at the next day's open / gap-informed exits (uses the option OPEN price = first trade of the day).
D2: India VIX filters and VIX-scaled strikes.
D3: conditional performance of the formula by regime.
All after 2 points of charges per trade. Periods: P1 2021-01..2025-08, P2 2025-09..now.
"""
import sys, os, importlib
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
F = importlib.import_module("13_formula_lab")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 120)
L = labm.Lab(start="2020-11-15")
P = {"P1": ("2021-01-04", "2025-08-29"), "P2": ("2025-09-01", "2099")}


def stats(g, col="net"):
    if len(g) == 0:
        return dict(n=0)
    eq = g[col].cumsum(); dd = (eq - eq.cummax()).min()
    return dict(n=len(g), net=g[col].sum(), dd=dd, worst=g[col].min(), win=(g[col] > 0).mean() * 100, avg=g[col].mean())


base = L.run(F.fbuilder(kc=0.75, kp=1.0, shift=0.15), "2021-01-04")
base["credit"] = base.short_prem
# ------------------------------------------------------------------ D1: exits using the next-day OPEN
def parse(legs):
    out = []
    for s in legs.split("/"):
        out.append((int(s[1:-1]), "CE" if s[-1] == "C" else "PE"))
    return out

rows = []
for r in base.itertuples():
    x = r.exit; e = r.expiry; oc = 0.0; cc = 0.0; zero = 0
    for k, o in parse(r.legs):
        q = L.q(x, e, o, k)
        op = q["open"] if q["open"] > 0 else q["close"]
        zero += int(q["open"] <= 0)
        oc += op; cc += q["close"]
    rows.append(dict(open_cost=oc, close_cost=cc, zero_open=zero))
b = pd.concat([base.reset_index(drop=True), pd.DataFrame(rows)], axis=1)
b["pl_close"] = b.credit - b.close_cost; b["pl_open"] = b.credit - b.open_cost; b["pl_mid"] = b.credit - 0.5 * (b.open_cost + b.close_cost)
print(f"D1. EXIT TIMING (formula trades; {len(b)} trades; legs with no open print: {int(b.zero_open.sum())})")
def exit_rule(b, tp=None, sl=None):
    pl = b.pl_close.copy()
    cap = (b.credit - b.open_cost) / b.credit
    take = pd.Series(False, index=b.index)
    if tp is not None: take |= cap >= tp
    if sl is not None: take |= b.open_cost >= sl * b.credit
    return pl.where(~take, b.pl_open)
variants = {"exit at next CLOSE (current)": b.pl_close, "exit at next OPEN": b.pl_open, "exit at midpoint of open & close (≈ midday)": b.pl_mid}
for tp in (0.4, 0.5, 0.6, 0.7): variants[f"at open: take profit if ≥{int(tp*100)}% captured, else hold to close"] = exit_rule(b, tp=tp)
for sl in (1.5, 2.0, 3.0): variants[f"at open: cut loss if cost ≥ {sl}× credit, else hold to close"] = exit_rule(b, sl=sl)
variants["at open: TP ≥50% captured OR loss ≥2× credit, else close"] = exit_rule(b, tp=0.5, sl=2.0)
rows = []
for nm, pl in variants.items():
    t = b.assign(net=pl - 2.0)
    r = {"rule": nm}
    for w, (a, z) in P.items():
        s = stats(t[(t.sell >= a) & (t.sell <= z)]); r.update({f"{w}_net": s["net"], f"{w}_dd": s["dd"], f"{w}_worst": s["worst"], f"{w}_win": s["win"]})
    rows.append(r)
print(pd.DataFrame(rows).round(1).to_string(index=False))
print("  by trade type, P2 (Sep25+): net at CLOSE vs at OPEN")
for n, g in b[b.sell >= "2025-09-01"].groupby("dte"):
    print(f"   {'Monday-type' if n == 1 else 'Friday-type'}: close {g.pl_close.sum()-2*len(g):8.1f} | open {g.pl_open.sum()-2*len(g):8.1f} | avg credit {g.credit.mean():.1f}, avg cost at open {g.open_cost.mean():.1f}, at close {g.close_cost.mean():.1f}")

# ------------------------------------------------------------------ D2: India VIX
v = pd.read_csv(os.path.join(ROOT, "data", "market", "vix_1d.csv"), parse_dates=["ts"])
v["day"] = v.ts.dt.strftime("%Y-%m-%d"); v = v.drop_duplicates("day").set_index("day").close
vd = v.pct_change() * 100; v5 = v.pct_change(5) * 100; vrel = v / v.rolling(60).mean()
b["vix"] = b.sell.map(v); b["vix_chg"] = b.sell.map(vd); b["vix_5d"] = b.sell.map(v5); b["vix_rel"] = b.sell.map(vrel)
b["net"] = b.pl_close - 2.0
print("\nD2. INDIA VIX at the time of selling")
print("   VIX level over the 611 trades: min", round(b.vix.min(), 1), "median", round(b.vix.median(), 1), "max", round(b.vix.max(), 1))
def bucket(col, edges, labels):
    return pd.cut(b[col], edges, labels=labels)
for col, edges, labels, title in (("vix", [0, 13, 16, 20, 99], ["<13", "13-16", "16-20", "20+"], "VIX level"),
                                  ("vix_chg", [-99, -3, 0, 3, 99], ["fell >3%", "fell 0-3%", "rose 0-3%", "rose >3%"], "VIX change on the day"),
                                  ("vix_rel", [0, 0.85, 1.0, 1.15, 9], ["<0.85×", "0.85-1.0×", "1.0-1.15×", ">1.15×"], "VIX vs its 60-day average")):
    print(f"   by {title} (net pts per trade, trades, win%, avg loss on 300+ pt nights is in the totals):")
    for lab, g in b.groupby(bucket(col, edges, labels), observed=True):
        gp1, gp2 = g[g.sell <= "2025-08-29"], g[g.sell >= "2025-09-01"]
        print(f"     {str(lab):12s} all {len(g):3d} trades avg {g.net.mean():6.2f} win {100*(g.net>0).mean():4.0f}% | 2021-Aug25 {len(gp1):3d} avg {gp1.net.mean():6.2f} | Sep25+ {len(gp2):3d} avg {gp2.net.mean():6.2f}")
print("   FILTER TESTS (skip the trade when the condition holds):")
rows = []
for nm, mask in {"skip if VIX rose >3% today": b.vix_chg > 3, "skip if VIX rose >5% today": b.vix_chg > 5, "skip if VIX ≥ 20": b.vix >= 20, "skip if VIX ≥ 18": b.vix >= 18,
                 "skip if VIX > 1.15× its 60d avg": b.vix_rel > 1.15, "skip if VIX < 12": b.vix < 12}.items():
    t = b[~mask.fillna(False)]; r = {"rule": nm}
    for w, (a, z) in P.items():
        s = stats(t[(t.sell >= a) & (t.sell <= z)]); r.update({f"{w}_n": s["n"], f"{w}_net": s["net"], f"{w}_dd": s["dd"]})
    rows.append(r)
s0 = {w: stats(b[(b.sell >= a) & (b.sell <= z)]) for w, (a, z) in P.items()}
rows.insert(0, {"rule": "no filter (current)", **{f"{w}_{k}": s0[w][k] for w in P for k in ("n", "net", "dd")}})
print(pd.DataFrame(rows).round(0).to_string(index=False))

# VIX-scaled strike distance
def vix_builder(gamma, ref="rel", kc=0.75, kp=1.0, shift=0.15):
    base_fn = None
    def s(Lb, i):
        d = Lb.days[i]; e = Lb.expiry(d)
        if e is None or Lb.dte(d, e) not in (1, 2): return None
        a = Lb.atm(d, e)
        if a is None: return None
        S = a[1] + a[2]; sp = Lb.spot[d]
        f = vrel.get(d, np.nan) if ref == "rel" else (v.get(d, np.nan) / 16.0)
        f = 1.0 if (f is None or np.isnan(f)) else f ** gamma
        j = Lb.allidx.index(d); c = sp + shift * (sp - Lb.idx.close.iloc[j - 5])
        ce = Lb.by_strike(d, e, "CE", c + kc * f * S); pe = Lb.by_strike(d, e, "PE", c - kp * f * S)
        if ce is None or pe is None: return None
        return labm.Position([labm.Leg(e, "CE", ce[0], -1, ce[1]), labm.Leg(e, "PE", pe[0], -1, pe[1])], exit="next_close")
    return s
print("\n   VIX-SCALED STRIKES (strike distance × (VIX ratio)^γ; γ=0 is the current formula):")
rows = []
for ref, gam in (("rel", 0.0), ("rel", 0.5), ("rel", 1.0), ("rel", 2.0), ("abs", 0.5), ("abs", 1.0)):
    t = L.run(vix_builder(gam, ref), "2021-01-04"); t["net"] = t.total - 2.0; r = {"scaling": f"{'VIX/60d-avg' if ref=='rel' else 'VIX/16'} ^ {gam}"}
    for w, (a, z) in P.items():
        s = stats(t[(t.sell >= a) & (t.sell <= z)]); r.update({f"{w}_net": s["net"], f"{w}_dd": s["dd"], f"{w}_worst": s["worst"]})
    rows.append(r)
print(pd.DataFrame(rows).round(0).to_string(index=False))

# ------------------------------------------------------------------ D3: conditional performance
print("\nD3. WHEN DOES THE FORMULA WORK BEST? net points per trade by condition at the time of selling (611 trades, after charges)")
y = pd.read_pickle("/tmp/claude-0/-home-user/8de82172-3b46-5df7-aff5-743e9a5a1393/scratchpad/ydaily.pkl")
y["day"] = y.index.strftime("%Y-%m-%d"); yy = y.set_index("day")
b["prev_abs"] = b.sell.map(yy.ar); b["r5"] = b.sell.map(yy.r5); b["rv20"] = b.sell.map(yy.rv20)
b["sratio"] = (b.credit / b.spot * 100)
def tab(col, edges, labels, title):
    print(f"   {title}")
    for lab, g in b.groupby(pd.cut(b[col], edges, labels=labels), observed=True):
        gp1, gp2 = g[g.sell <= "2025-08-29"], g[g.sell >= "2025-09-01"]
        print(f"     {str(lab):16s} {len(g):3d} trades | avg {g.net.mean():6.2f} win {100*(g.net>0).mean():3.0f}% worst {g.net.min():7.1f} | 2021-Aug25: {len(gp1):3d} avg {gp1.net.mean():6.2f} | Sep25+: {len(gp2):3d} avg {gp2.net.mean():6.2f}")
tab("prev_abs", [-1, 0.4, 0.8, 1.3, 99], ["quiet (<0.4%)", "normal 0.4-0.8%", "active 0.8-1.3%", "big (>1.3%)"], "by TODAY'S move (the day you sell)")
tab("r5", [-99, -2.5, -0.5, 0.5, 2.5, 99], ["down >2.5%", "down 0.5-2.5%", "flat ±0.5%", "up 0.5-2.5%", "up >2.5%"], "by the 5-day trend")
tab("rv20", [0, 0.45, 0.65, 0.9, 9], ["calm 20d (<0.45%)", "0.45-0.65%", "0.65-0.9%", "wild 20d (>0.9%)"], "by 20-day average move")
tab("sratio", [0, 1.0, 1.6, 2.2, 99], ["premium <1.0% spot", "1.0-1.6%", "1.6-2.2%", ">2.2% spot"], "by the premium collected as % of Nifty")
b["wd"] = pd.to_datetime(b.sell).dt.dayofweek
print("   by sell weekday (all 611):", {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][k]: (len(g), round(g.net.mean(), 2)) for k, g in b.groupby('wd')})
b["mon"] = pd.to_datetime(b.sell).dt.month
print("   by month of year (avg net pts/trade):", {k: round(g.net.mean(), 1) for k, g in b.groupby('mon')})
b.to_csv(os.path.join(ROOT, "results", "manual", "pattern_strategy_trades.csv"), index=False, float_format="%.3f")
