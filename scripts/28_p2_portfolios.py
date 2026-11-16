"""Combine the candidate pieces into weekly plans and compare on P2 (Sep 2025 -> Nov 2026). Charges 1 pt/leg/lot."""
import sys, os, importlib, pandas as pd, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
P = importlib.import_module("25_p2_lab")
pd.set_option("display.width", 260); pd.set_option("display.max_rows", 200)
FRI = dict(dtes={2}, exit="next", sel="S", kc=0.75, kp=1.0, sh=0.15)
MON = dict(dtes={1}, exit="next", sel="S", kc=0.75, kp=1.0, sh=0.15)
MON_C25 = dict(MON, kc=0.25)
MON_C0 = dict(MON, kc=0.0)
THU = dict(dtes={3}, exit="expiry", sel="S", kc=1.0, kp=1.0, sh=0.15, stop=3.0)     # middle-of-grid, not the best one
THU_B = dict(dtes={3}, exit="expiry", sel="S", kc=0.5, kp=1.0, sh=0.15, stop=2.0)   # best in grid (optimistic)
cache = {}
def tr(name, spec, lots=1.0):
    if name not in cache: cache[name] = P.run(spec).assign(piece=name)
    t = cache[name].copy(); t["net"] *= lots; t["pnl"] *= lots; t["credit"] *= lots; t["lots"] = lots; return t
PLANS = {
 "A current: Fri 1 + Mon 1": [("FRI", FRI, 1), ("MON", MON, 1)],
 "B Mon call closer (0.25 S)": [("FRI", FRI, 1), ("MON_C25", MON_C25, 1)],
 "C Fri 2 lots + Mon 1": [("FRI", FRI, 2), ("MON", MON, 1)],
 "D current + Thu->Tue hold": [("FRI", FRI, 1), ("MON", MON, 1), ("THU", THU, 1)],
 "E Fri 2 + Mon call 0.25 + Thu hold": [("FRI", FRI, 2), ("MON_C25", MON_C25, 1), ("THU", THU, 1)],
 "F current x2 lots (same capital as D/E)": [("FRI", FRI, 2), ("MON", MON, 2)],
}
rows, monthly = [], {}
for nm, parts in PLANS.items():
    t = pd.concat([tr(a, s, k) for a, s, k in parts]).sort_values("exit")
    eq = t.groupby("exit").net.sum().cumsum(); dd = (eq - eq.cummax()).min()
    m = t.groupby(t.exit.str[:7]).net.sum(); monthly[nm[:1]] = m
    by_exit = t.groupby("exit").net.sum()
    w3 = by_exit.nsmallest(3)
    rows.append(dict(plan=nm, trades=len(t), net=round(t.net.sum()), rupees=round(t.net.sum() * 65), worst_day=round(by_exit.min()),
                     worst3_days=round(w3.sum()), net_ex_worst3_days=round(t.net.sum() - w3.sum()), max_dd=round(dd), worst_month=round(m.min()),
                     months_pos=f"{(m > 0).sum()}/{len(m)}", H1=round(t[t.sell <= P.H1_END].net.sum()), H2=round(t[t.sell > P.H1_END].net.sum())))
print(pd.DataFrame(rows).to_string(index=False))
print("\nMonthly net points by plan (by exit month):")
print(pd.DataFrame(monthly).round(0).fillna(0).astype(int).to_string())
th = tr("THU", THU)
print("\nThu->Tue hold (1.0/1.0, stop 3x) detail: n", len(th), "net", round(th.net.sum()), "stopped", int((th.exit != th.expiry).sum()))
print(th.nsmallest(6, "net")[["sell", "exit", "expiry", "spot", "S", "credit", "legs", "move", "net"]].round(1).to_string(index=False))
thb = tr("THU_B", THU_B); print("best-grid Thu variant (0.5/1.0, stop 2x): net", round(thb.net.sum()))
