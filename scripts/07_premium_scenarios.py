"""Premium-level scenarios for the overnight strangle (Tuesday-expiry period).

Rules (same as the manual ₹30 study):
  - each trading day from START, nearest expiry strictly after today
  - only strikes that traded that day (contracts > 0)
  - sell CE and PE at the close, buy back the same strikes at the next trading day's close
  - points only, no costs
Selection:
  - ("range", lo, hi): strike whose close is in [lo, hi], closest to the mid; skip the day if
    either side has none
  - ("nearest", x): strike whose close is nearest x (always trades)
Writes results/manual/premium_scenarios_summary.csv and premium_scenarios_trades.csv
"""
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "manual")
START = "2025-09-01"

SCENARIOS = [("nearest", x) for x in (10, 15, 20, 25, 30, 35, 40, 50, 60, 75, 100)] + \
            [("range", a, b) for a, b in ((10, 15), (15, 20), (20, 25), (25, 30), (30, 35), (35, 40),
                                          (40, 45), (45, 50), (50, 60), (60, 75), (75, 100))]


def name(sc):
    return f"Nearest ₹{sc[1]}" if sc[0] == "nearest" else f"₹{sc[1]}–{sc[2]}"


def load():
    op = pd.read_csv(os.path.join(ROOT, "data", "nifty_options_all.csv.gz"),
                     usecols=["date", "expiry", "strike", "opt", "close", "contracts"])
    idx = pd.read_csv(os.path.join(ROOT, "data", "nifty_index.csv")).set_index("date").close
    days = sorted(op.date.unique())
    sel_days = [d for d in days if d >= START][:-1]
    op = op[op.date >= START]
    by_day = {d: g for d, g in op.groupby("date")}
    plan = []
    for d in sel_days:
        n = days[days.index(d) + 1]
        g = by_day[d]
        e = min(v for v in g.expiry.unique() if v > d)
        today = g[(g.expiry == e) & (g.contracts > 0)]
        nxt = by_day[n]
        nxt = nxt[nxt.expiry == e].set_index(["strike", "opt"])
        dte = sum(1 for x in days if d < x <= e)
        if e > days[-1]:  # expiry beyond the data: add weekdays after the last day
            dte += int(np.busday_count(np.datetime64(days[-1]) + 1, np.datetime64(e) + 1))
        plan.append(dict(sell=d, buy=n, expiry=e, dte=dte, spot=idx[d], move=idx[n] - idx[d],
                         chain={o: today[today.opt == o][["strike", "close"]].values for o in ("CE", "PE")},
                         nxt=nxt.close.to_dict()))
    return plan


def pick(arr, sc):
    k, c = arr[:, 0], arr[:, 1]
    if sc[0] == "nearest":
        target, ok = sc[1], np.ones(len(c), bool)
    else:
        lo, hi = sc[1], sc[2]
        target, ok = (lo + hi) / 2, (c >= lo) & (c <= hi)
    if not ok.any():
        return None
    i = np.where(ok)[0]
    j = i[np.argmin(np.abs(c[i] - target))]
    return k[j], c[j]


def run(plan, sc):
    rows, skipped = [], 0
    for p in plan:
        legs = {}
        for o in ("CE", "PE"):
            r = pick(p["chain"][o], sc)
            if r is None or (r[0], o) not in p["nxt"]:
                legs = None
                break
            legs[o] = (r[0], r[1], p["nxt"][(r[0], o)])
        if legs is None:
            skipped += 1
            continue
        ce, pe = legs["CE"], legs["PE"]
        rows.append(dict(scenario=name(sc), sell=p["sell"], buy=p["buy"], expiry=p["expiry"], dte=p["dte"],
                         spot=p["spot"], move=round(p["move"], 2),
                         ce_strike=int(ce[0]), ce_sell=ce[1], ce_buy=ce[2], ce_pnl=round(ce[1] - ce[2], 2),
                         pe_strike=int(pe[0]), pe_sell=pe[1], pe_buy=pe[2], pe_pnl=round(pe[1] - pe[2], 2)))
    t = pd.DataFrame(rows)
    t["total"] = t.ce_pnl + t.pe_pnl
    return t, skipped


def summarize(sc, t, skipped):
    eq = t.total.cumsum()
    m = t.groupby(t.sell.str[:7]).total.sum()
    big = t.move.abs() >= 300
    return dict(
        scenario=name(sc), kind=sc[0], trades=len(t), skipped=skipped,
        avg_premium=(t.ce_sell + t.pe_sell).mean(), total=t.total.sum(), avg=t.total.mean(),
        win_rate=(t.total > 0).mean(), avg_win=t.total[t.total > 0].mean(), avg_loss=t.total[t.total < 0].mean(),
        worst=t.total.min(), best=t.total.max(), max_dd=(eq - eq.cummax()).min(),
        months_pos=int((m > 0).sum()), months=len(m),
        sep_dec25=t[t.sell < "2026-01-01"].total.sum(), y2026=t[t.sell >= "2026-01-01"].total.sum(),
        dte12=t[t.dte <= 2].total.sum(), dte3p=t[t.dte >= 3].total.sum(), dte1=t[t.dte == 1].total.sum(),
        big_moves=t[big].total.sum(), small_moves=t[~big].total.sum(),
        ce=t.ce_pnl.sum(), pe=t.pe_pnl.sum(), keep_pct=t.total.sum() / (t.ce_sell + t.pe_sell).sum(),
        **{f"m_{k}": v for k, v in m.items()},
    )


def main():
    os.makedirs(OUT, exist_ok=True)
    plan = load()
    summ, trades = [], []
    for sc in SCENARIOS:
        t, sk = run(plan, sc)
        trades.append(t)
        summ.append(summarize(sc, t, sk))
        print(f"{name(sc):14s} trades={len(t):4d} skipped={sk:4d} total={t.total.sum():9.2f}", flush=True)
    pd.DataFrame(summ).to_csv(os.path.join(OUT, "premium_scenarios_summary.csv"), index=False, float_format="%.2f")
    pd.concat(trades).to_csv(os.path.join(OUT, "premium_scenarios_trades.csv"), index=False, float_format="%.2f")


if __name__ == "__main__":
    main()
