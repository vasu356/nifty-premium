"""Dataset for the "which extra days to sell" study.

For every trading day d (2021-01 .. last day with a next-day close) and the nearest expiry (dte 1..5) it records
  * the outcome (points, before charges) of several strike rules, sold at close d and bought back at close d+1
  * features known at the close of d (implied move, realised vol, gap, intraday shape, VIX, trend, OI/PCR ...)

Strike rules ("cfg"):
  F{kc}_{kp}  : centre = spot + 0.15*(spot - spot 5 trading days ago); call = centre + kc*S, put = centre - kp*S
                (S = ATM straddle close of that day, so the distance already scales with days to expiry)
  P30         : call and put whose close is nearest Rs30 (OTM side)
Writes results/manual/extra_day_trades.csv.gz and results/manual/extra_day_features.csv.
"""
import os, sys, importlib
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "manual")
M = os.path.join(ROOT, "data", "market_user")
CFGS = {f"F{kc}_{kp}": (kc, kp) for kc, kp in [(0.5, 0.75), (0.75, 1.0), (1.0, 1.0), (1.0, 1.25), (1.25, 1.5), (1.5, 1.5), (2.0, 2.0)]}

L = labm.Lab(start="2020-11-15")
spot = L.spot


def daily_features():
    d = pd.read_csv(os.path.join(M, "nifty50_1day.csv"))
    d["date"] = d.datetime.str[:10]
    d = d.set_index("date")[["open", "high", "low", "close"]]
    v = pd.read_csv(os.path.join(ROOT, "data", "market", "vix_1d.csv"))
    v["date"] = v.ts.str[:10]
    v = v.set_index("date").close.rename("vix")
    d = d.join(v)
    # intraday shape from 30-min bars: last hour move/range, first hour range
    m = pd.read_csv(os.path.join(M, "nifty50_30min.csv"))
    m["date"] = m.datetime.str[:10]
    g = m.groupby("date")
    last2 = g.tail(2).groupby("date").agg(l_hi=("high", "max"), l_lo=("low", "min"))
    last_open = g.tail(2).groupby("date").open.first()
    first2 = g.head(2).groupby("date").agg(f_hi=("high", "max"), f_lo=("low", "min"))
    d = d.join(last2).join(last_open.rename("l_open")).join(first2)
    f = pd.DataFrame(index=d.index)
    c = d.close
    pc = c.shift(1)
    f["ret1p"] = (c / pc - 1) * 100
    f["absret1p"] = f.ret1p.abs()
    f["gap_p"] = (d.open / pc - 1) * 100
    f["abs_gap_p"] = f.gap_p.abs()
    f["range_p"] = (d.high - d.low) / pc * 100
    f["body_p"] = (c - d.open) / pc * 100
    f["close_pos"] = (c - d.low) / (d.high - d.low).replace(0, np.nan)
    f["last_hr_p"] = (c - d.l_open) / pc * 100
    f["last_hr_range_p"] = (d.l_hi - d.l_lo) / pc * 100
    f["first_hr_range_p"] = (d.f_hi - d.f_lo) / pc * 100
    for n in (2, 3, 5, 10, 20):
        f[f"retn{n}p"] = (c / c.shift(n) - 1) * 100
    r = c.pct_change() * 100
    for n in (5, 10, 20, 60):
        f[f"rv{n}"] = r.abs().rolling(n).mean()          # mean |daily move| %
    f["rv5_20"] = f.rv5 / f.rv20
    f["rng5"] = f.range_p.rolling(5).mean()
    f["rng20"] = f.range_p.rolling(20).mean()
    f["dist_ma20_p"] = (c / c.rolling(20).mean() - 1) * 100
    f["dist_ma50_p"] = (c / c.rolling(50).mean() - 1) * 100
    f["dd_high20_p"] = (c / c.rolling(20).max() - 1) * 100
    f["vix"] = d.vix
    f["vix_chg1p"] = (d.vix / d.vix.shift(1) - 1) * 100
    f["vix_rel20"] = d.vix / d.vix.rolling(20).mean()
    f["vix_rel60"] = d.vix / d.vix.rolling(60).mean()
    f["vix_pct250"] = d.vix.rolling(250).apply(lambda x: (x[-1] >= x).mean(), raw=True)
    f["big_move_5d"] = (r.abs() > 1.2).rolling(5).sum()
    f["dow"] = pd.to_datetime(f.index).dayofweek
    return f


def chain_features(d, e, n):
    at = L.atm(d, e)
    if at is None:
        return None
    S = at[1] + at[2]
    sp = spot[d]
    row = dict(S=S, atm=at[0], imp_p=S / sp * 100, imp_day_p=S / sp * 100 / np.sqrt(n))
    ce, pe = L.chain.get((d, e, "CE")), L.chain.get((d, e, "PE"))
    if ce is not None and pe is not None:
        row["pcr_oi"] = pe["oi"].sum() / max(ce["oi"].sum(), 1)
        row["pcr_vol"] = pe["contracts"].sum() / max(ce["contracts"].sum(), 1)
        w = ce["oi"] * (np.abs(ce["strike"] - sp) < 4 * S)
        row["ce_wall_dist_S"] = (ce["strike"][np.argmax(w)] - sp) / S if w.max() > 0 else np.nan
        w = pe["oi"] * (np.abs(pe["strike"] - sp) < 4 * S)
        row["pe_wall_dist_S"] = (sp - pe["strike"][np.argmax(w)]) / S if w.max() > 0 else np.nan
    c1 = L.by_strike(d, e, "CE", sp + S)
    p1 = L.by_strike(d, e, "PE", sp - S)
    if c1 and p1:
        row["skew_pc"] = p1[1] / max(c1[1], 0.05)
    return row


def outcome(i, cfg, e, S, d):
    sp = spot[d]
    j = L.allidx.index(d)
    tr = 0.15 * (L.idx.close.iloc[j] - L.idx.close.iloc[j - 5])
    if cfg == "P30":
        ce = L.by_price(d, e, "CE", 30, otm_of=sp)
        pe = L.by_price(d, e, "PE", 30, otm_of=sp)
    else:
        kc, kp = CFGS[cfg]
        ce = L.by_strike(d, e, "CE", sp + tr + kc * S)
        pe = L.by_strike(d, e, "PE", sp + tr - kp * S)
    if ce is None or pe is None:
        return None
    x = L.days[i + 1]
    qc, qp = L.q(x, e, "CE", ce[0]), L.q(x, e, "PE", pe[0])
    if qc is None or qp is None:
        return None
    return dict(ce_k=ce[0], pe_k=pe[0], credit=ce[1] + pe[1], pnl=ce[1] + pe[1] - qc["close"] - qp["close"],
                ce_pnl=ce[1] - qc["close"], pe_pnl=pe[1] - qp["close"])


def main():
    F = daily_features()
    rows, frows = [], []
    for i, d in enumerate(L.days[:-1]):
        if d < "2021-01-04":
            continue
        e = L.expiry(d)
        if e is None:
            continue
        n = L.dte(d, e)
        if n > 5:
            continue
        cf = chain_features(d, e, n)
        if cf is None:
            continue
        frows.append(dict(sell=d, exit=L.days[i + 1], expiry=e, dte=n, spot=spot[d], move=spot[L.days[i + 1]] - spot[d], **cf))
        for cfg in list(CFGS) + ["P30"]:
            o = outcome(i, cfg, e, cf["S"], d)
            if o:
                rows.append(dict(sell=d, dte=n, cfg=cfg, **o))
    T = pd.DataFrame(rows)
    Fm = pd.DataFrame(frows).merge(F.rename_axis("sell").reset_index(), on="sell", how="left")
    os.makedirs(OUT, exist_ok=True)
    T.to_csv(os.path.join(OUT, "extra_day_trades.csv.gz"), index=False, float_format="%.3f")
    Fm.to_csv(os.path.join(OUT, "extra_day_features.csv"), index=False, float_format="%.4f")
    print(len(T), "trades", len(Fm), "days;", Fm.sell.min(), Fm.sell.max())
    print(T.groupby(["dte", "cfg"]).size().unstack())


if __name__ == "__main__":
    main()
