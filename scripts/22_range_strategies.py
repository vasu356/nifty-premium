"""Ideas 2+3 on out-of-sample days (2023-01 onward), net of 2 points per trade, sold at close, bought back next close.
(2) gate: formula strikes (F0.75_1.0) but trade only when option-implied move / forecast move is high (market over-pricing)
(3) strikes from the forecast range: call = centre + kc*k*f*spot, put = centre - kp*k*f*spot, f = forecast mean |next-day move| %
Strike variants are compared at similar premium (credit) with the straddle-based formula."""
import os, sys, importlib, numpy as np, pandas as pd
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(ROOT, "results", "manual")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
L = labm.Lab(start="2020-11-15")
FD = pd.read_csv(os.path.join(R, "range_daily.csv"), index_col=0)
EF = pd.read_csv(os.path.join(R, "extra_day_features.csv"))
ET = pd.read_csv(os.path.join(R, "extra_day_trades.csv.gz"))
base = ET[ET.cfg == "F0.75_1.0"].merge(EF[["sell", "imp_day_p", "imp_p", "S", "dist_ma20_p"]], on="sell")
base = base.merge(FD[["f_vix", "f_har", "f_harvix", "f_gbm"]], left_on="sell", right_index=True)
base = base[base.sell >= "2023-01-01"].copy(); base["net"] = base.pnl - 2; base["yr"] = base.sell.str[:4]
base["credit_r"] = base.credit

def run_strikes(row, f, k, kc=1.0, kp=1.0):
    d = row.sell; sp = L.spot[d]; i = L.pos[d]; e = L.expiry(d)
    j = L.allidx.index(d); tr = 0.15 * (L.idx.close.iloc[j] - L.idx.close.iloc[j - 5])
    dist = k * f / 100 * sp
    ce = L.by_strike(d, e, "CE", sp + tr + kc * dist); pe = L.by_strike(d, e, "PE", sp + tr - kp * dist)
    if ce is None or pe is None: return None
    x = L.days[i + 1]; qc, qp = L.q(x, e, "CE", ce[0]), L.q(x, e, "PE", pe[0])
    if qc is None or qp is None: return None
    return dict(credit=ce[1] + pe[1], pnl=ce[1] + pe[1] - qc["close"] - qp["close"], breach=(L.spot[x] > ce[0]) or (L.spot[x] < pe[0]))

def summ(t, label):
    t = t.sort_values("sell"); eq = t.net.cumsum()
    return dict(rule=label, n=len(t), credit=t.credit.mean(), net=t.net.sum(), avg=t.net.mean(), keep_pct=t.net.sum() / t.credit.sum() * 100, win=(t.net > 0).mean() * 100,
                worst=t.net.min(), dd=(eq - eq.cummax()).min(), **{y: round(t[t.yr == y].net.sum()) for y in ("2023", "2024", "2025", "2026")})

for label, dtes in (("FORMULA DAYS (Fri/Mon, dte 1-2)", [1, 2]), ("EXTRA DAYS (Tue/Wed/Thu, dte 3-5)", [3, 4, 5])):
    b = base[base.dte.isin(dtes)].copy()
    print(f"\n######## {label}: {len(b)} OOS trades")
    print("--- IDEA 2: formula strikes, trade only when implied/forecast is high (forecast = HAR+VIX model f_harvix)")
    b["ratio"] = b.imp_day_p / b.f_harvix
    rows = [summ(b, "all trades (current)")]
    qs = b.ratio.quantile([1/3, 2/3]).values
    rows += [summ(b[b.ratio <= qs[0]], f"ratio low third (<= {qs[0]:.2f})"), summ(b[(b.ratio > qs[0]) & (b.ratio <= qs[1])], "ratio middle third"), summ(b[b.ratio > qs[1]], f"ratio high third (> {qs[1]:.2f})")]
    print(pd.DataFrame(rows).round(1).to_string(index=False))
    print("--- IDEA 3: strikes from forecast range (symmetric k x forecast move), vs straddle-based formula")
    rows = [summ(b, "FORMULA (straddle-based 0.75/1.0 S)")]
    for fn in ("f_harvix", "f_vix"):
        for k in (1.5, 2.0, 2.5, 3.0, 3.5):
            res = []
            for r in b.itertuples():
                o = run_strikes(r, getattr(r, fn), k, kc=0.75, kp=1.0)
                if o: res.append(dict(sell=r.sell, yr=r.yr, credit=o["credit"], net=o["pnl"] - 2))
            t = pd.DataFrame(res); rows.append(summ(t, f"{fn} k={k}"))
    print(pd.DataFrame(rows).round(1).to_string(index=False))
