"""Can previous-day / previous-week patterns predict the next day's Nifty range?  Target = next trading day's
(high-low)/prev close % (range) and |close-close| %. Reports (A) pattern table, (B) weekly structure, (C) walk-forward models by target weekday."""
import os, warnings, numpy as np, pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); R = os.path.join(ROOT, "results", "manual"); M = os.path.join(ROOT, "data", "market_user")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)
d = pd.read_csv(os.path.join(M, "nifty50_1day.csv")); d["date"] = d.datetime.str[:10]; d = d.set_index("date")[["open", "high", "low", "close"]]
v = pd.read_csv(os.path.join(ROOT, "data", "market", "vix_1d.csv")); v["date"] = v.ts.str[:10]; d["vix"] = v.set_index("date").close
op = pd.read_csv(os.path.join(ROOT, "data", "nifty_options_all.csv.gz"), usecols=["date", "expiry"]); exps = np.array(sorted(op.expiry.unique()))
days = list(d.index); pos = {x: i for i, x in enumerate(days)}
def dte_of(x):
    e = exps[exps >= x][0]; return sum(1 for y in days[pos[x]:] if y <= e) - 1     # 0 = expiry day
c, h, l, o = d.close, d.high, d.low, d.open; pc = c.shift(1)
f = pd.DataFrame(index=d.index)
f["rng"] = (h - l) / pc * 100; f["absr"] = (c / pc - 1).abs() * 100; f["ret"] = (c / pc - 1) * 100
f["gap"] = (o / pc - 1) * 100; f["body"] = (c - o) / pc * 100; f["abody"] = f.body.abs()
f["cpos"] = (c - l) / (h - l).replace(0, np.nan)
for n in (5, 20): f[f"rng{n}"] = f.rng.rolling(n).mean(); f[f"a{n}"] = f.absr.rolling(n).mean()
f["rng_rel"] = f.rng / f.rng20
f["vix"] = d.vix; f["vixd"] = d.vix / np.sqrt(252)
f["inside"] = ((h < h.shift(1)) & (l > l.shift(1))).astype(int); f["outside"] = ((h > h.shift(1)) & (l < l.shift(1))).astype(int)
f["nr7"] = (f.rng <= f.rng.rolling(7).min()).astype(int); f["nr4"] = (f.rng <= f.rng.rolling(4).min()).astype(int)
f["bigrng"] = (f.rng_rel > 1.5).astype(int); f["smallrng"] = (f.rng_rel < 0.7).astype(int)
f["biggap"] = (f.gap.abs() > 0.5).astype(int); f["doji"] = ((f.abody / f.rng) < 0.25).astype(int)
f["trend_up"] = ((f.cpos > 0.8) & (f.rng_rel > 1)).astype(int); f["trend_dn"] = ((f.cpos < 0.2) & (f.rng_rel > 1)).astype(int)
f["two_narrow"] = (f.smallrng.astype(bool) & f.smallrng.shift(1).fillna(0).astype(bool)).astype(int)
sgn = np.sign(f.ret); f["up3"] = ((sgn > 0) & (sgn.shift(1) > 0) & (sgn.shift(2) > 0)).astype(int); f["dn3"] = ((sgn < 0) & (sgn.shift(1) < 0) & (sgn.shift(2) < 0)).astype(int)
f["lowvix_squeeze"] = (f.vix < f.vix.rolling(60).quantile(0.2)).astype(int)
# weekly structure
dt = pd.to_datetime(f.index); f["wk"] = dt.to_period("W-SUN").astype(str); f["dow"] = dt.dayofweek
g = f.groupby("wk"); wk_h = g.apply(lambda x: pd.Series(h.loc[x.index].max(), index=x.index)).droplevel(0); wk_l = g.apply(lambda x: pd.Series(l.loc[x.index].min(), index=x.index)).droplevel(0)
wtd_h = h.groupby(f.wk).cummax(); wtd_l = l.groupby(f.wk).cummin()
f["wtd_rng"] = (wtd_h - wtd_l) / pc.groupby(f.wk).transform("first") * 100
wk_first_close = pc.groupby(f.wk).transform("first")
f["wtd_ret"] = (c / wk_first_close - 1) * 100; f["wtd_pos"] = (c - wtd_l) / (wtd_h - wtd_l).replace(0, np.nan)
wk = pd.DataFrame({"h": h.groupby(f.wk).max(), "l": l.groupby(f.wk).min(), "c": c.groupby(f.wk).last(), "p": pc.groupby(f.wk).first()})
wk["rng"] = (wk.h - wk.l) / wk.p * 100; wk["ret"] = (wk.c / wk.p - 1) * 100
f["prevwk_rng"] = f.wk.map(wk.rng.shift(1)); f["prevwk_aret"] = f.wk.map(wk.ret.shift(1).abs()); f["prevwk_rng_rel"] = f.prevwk_rng / f.wk.map(wk.rng.rolling(8).mean().shift(1))
f["dte_t"] = [dte_of(days[min(pos[x] + 1, len(days) - 1)]) for x in f.index]
nxt = pd.Series(days, index=days).shift(-1); f["next_date"] = nxt; f["dow_t"] = pd.to_datetime(nxt).dt.dayofweek
f["y_rng"] = f.rng.shift(-1); f["y_abs"] = f.absr.shift(-1)
f = f[(f.index >= "2021-03-15") & (f.index < days[-1])].dropna(subset=["rng20", "y_rng", "prevwk_rng_rel", "vix"]).copy()
DOW = {0: "Mon", 1: "Tue", 2: "Wed", 3: "Thu", 4: "Fri"}
print(f"rows {len(f)}; mean next-day range {f.y_rng.mean():.3f}%  mean |ret| {f.y_abs.mean():.3f}%")
print("\n(A0) next-day range % by target weekday & era (expiry Thu until Aug 2025, Tue after):")
f["era"] = np.where(f.index <= "2025-08-29", "2021-25 (Thu exp)", "Sep25+ (Tue exp)")
print(f.pivot_table(index="dow_t", columns="era", values="y_rng", aggfunc="mean").rename(index=DOW).round(3))
print("\n(A1) next-day range % by days-to-expiry of the TARGET day (0 = expiry day):")
print(f.groupby(["era", "dte_t"]).y_rng.agg(["mean", "size"]).round(3).unstack(0))
print("\n(A2) PATTERN TABLE: next-day range, ratio vs all days; consistent across 2021-23 vs 2024-26?")
PAT = ["inside", "outside", "nr7", "nr4", "bigrng", "smallrng", "biggap", "doji", "trend_up", "trend_dn", "two_narrow", "up3", "dn3", "lowvix_squeeze"]
base = f.y_rng.mean(); e1 = f[f.index < "2024-01-01"]; e2 = f[f.index >= "2024-01-01"]; rows = []
for p in PAT:
    s = f[f[p] == 1]; s1 = e1[e1[p] == 1]; s2 = e2[e2[p] == 1]
    rows.append(dict(pattern=p, n=len(s), next_rng=s.y_rng.mean(), ratio=s.y_rng.mean() / base, ratio_21_23=s1.y_rng.mean() / e1.y_rng.mean(), ratio_24_26=s2.y_rng.mean() / e2.y_rng.mean(), next_abs_ratio=s.y_abs.mean() / f.y_abs.mean()))
print(pd.DataFrame(rows).round(2).to_string(index=False))
print("\n(A3) Does next day stay inside previous day's high-low? (share of days)")
ph, pl = h.reindex(f.index), l.reindex(f.index); nh = h.shift(-1).reindex(f.index); nl = l.shift(-1).reindex(f.index); nc = c.shift(-1).reindex(f.index)
print({"next close inside prev H-L": round(((nc <= ph) & (nc >= pl)).mean(), 3), "next H-L fully inside prev H-L": round(((nh <= ph) & (nl >= pl)).mean(), 3), "next high > prev high": round((nh > ph).mean(), 3), "next low < prev low": round((nl < pl).mean(), 3)})
print("\n(B) WEEKLY STRUCTURE: Spearman corr with next-day range, by target weekday")
FEAT_B = ["rng", "rng_rel", "a5", "a20", "vixd", "prevwk_rng", "prevwk_rng_rel", "prevwk_aret", "wtd_rng", "wtd_ret", "wtd_pos", "abody", "gap"]
rows = []
for dw in (1, 2, 3):
    s = f[f.dow_t == dw]
    rows.append(dict(target=DOW[dw], n=len(s), **{k: round(s[[k, "y_rng"]].corr(method="spearman").iloc[0, 1], 2) for k in FEAT_B}))
print(pd.DataFrame(rows).to_string(index=False))
BLK = [("2023-01-01", "2023-07-01"), ("2023-07-01", "2024-01-01"), ("2024-01-01", "2024-07-01"), ("2024-07-01", "2025-01-01"), ("2025-01-01", "2025-07-01"), ("2025-07-01", "2026-01-01"), ("2026-01-01", "2027-01-01")]
BASEF = ["rng5", "rng20", "a5", "a20", "vixd", "rng"]
PATF = BASEF + ["rng_rel", "abody", "cpos", "gap", "inside", "outside", "nr7", "bigrng", "smallrng", "biggap", "doji", "trend_up", "trend_dn", "two_narrow", "up3", "dn3", "prevwk_rng", "prevwk_rng_rel", "prevwk_aret", "wtd_rng", "wtd_ret", "wtd_pos", "dte_t", "dow_t"]
mk_r = lambda: make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-1, 3, 12)))
mk_g = lambda: GradientBoostingRegressor(n_estimators=150, max_depth=2, learning_rate=0.04, subsample=0.7, min_samples_leaf=30, random_state=0)
for nm, feats, mk in (("base(vol+vix)", BASEF, mk_r), ("vol+vix+patterns Ridge", PATF, mk_r), ("vol+vix+patterns GBM", PATF, mk_g)):
    out = pd.Series(np.nan, index=f.index)
    for a, b in BLK:
        tr = f[f.next_date < a].dropna(subset=feats + ["y_rng"]); te = f[(f.index >= a) & (f.index < b)]
        if len(te): out.loc[te.index] = mk().fit(tr[feats], tr.y_rng).predict(te[feats].fillna(tr[feats].median()))
    f["p_" + nm] = out
O = f[f.index >= "2023-01-01"].dropna(subset=["p_base(vol+vix)"]).copy()
print("\n(C) WALK-FORWARD forecast of next-day RANGE % (out of sample 2023+): R2 and MAE by TARGET weekday")
rows = []
for dw in (None, 1, 2, 3):
    s = O if dw is None else O[O.dow_t == dw]; r = dict(target="all" if dw is None else DOW[dw], n=len(s), mean_actual=s.y_rng.mean())
    for nm in ("base(vol+vix)", "vol+vix+patterns Ridge", "vol+vix+patterns GBM"):
        e = s.y_rng - s["p_" + nm]; r["R2 " + nm] = 1 - (e ** 2).sum() / ((s.y_rng - s.y_rng.mean()) ** 2).sum(); r["MAE " + nm.split(" ")[0] + nm[-5:]] = e.abs().mean()
    rows.append(r)
print(pd.DataFrame(rows).round(3).to_string(index=False))
O.to_csv(os.path.join(R, "range_pattern_forecasts.csv"), float_format="%.4f")
