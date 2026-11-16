"""Ideas 1+2: can we forecast next-day move size better than the options (and VIX) already imply?
Targets (close(d) -> close(d+1)): a = |ret| %, and signed ret %.
Walk-forward (half-year blocks from 2023-01, trained only on rows whose target date is before the block).
Outputs results/manual/range_daily.csv (features + OOS forecasts) for the later strategy tests."""
import os, warnings, numpy as np, pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.linear_model import RidgeCV, LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
warnings.filterwarnings("ignore")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "results", "manual"); M = os.path.join(ROOT, "data", "market_user")
pd.set_option("display.width", 250); pd.set_option("display.max_rows", 200)

d = pd.read_csv(os.path.join(M, "nifty50_1day.csv")); d["date"] = d.datetime.str[:10]; d = d.set_index("date")[["open", "high", "low", "close"]]
v = pd.read_csv(os.path.join(ROOT, "data", "market", "vix_1d.csv")); v["date"] = v.ts.str[:10]; d["vix"] = v.set_index("date").close
# intraday realised variance from 5-minute closes
m5 = pd.read_csv(os.path.join(M, "nifty50_5min.csv")); m5["date"] = m5.datetime.str[:10]; m5["t"] = m5.datetime.str[11:16]
m5 = m5[(m5.t >= "09:15") & (m5.t <= "15:25")]
m5["lr"] = np.log(m5.close).groupby(m5.date).diff()
g = m5.groupby("date")
d["rv5m"] = np.sqrt(g.lr.apply(lambda s: (s.dropna() ** 2).sum())) * 100
d["rv5m_lasthr"] = np.sqrt(m5[m5.t >= "14:25"].groupby("date").lr.apply(lambda s: (s.dropna() ** 2).sum())) * 100
d["rv5m_first"] = np.sqrt(m5[m5.t <= "10:15"].groupby("date").lr.apply(lambda s: (s.dropna() ** 2).sum())) * 100
c = d.close; pc = c.shift(1); r = (c / pc - 1) * 100
f = pd.DataFrame(index=d.index)
f["ret"] = r; f["absr"] = r.abs()
f["gap"] = (d.open / pc - 1) * 100; f["absgap"] = f.gap.abs()
f["pk"] = np.log(d.high / d.low) * 100                     # Parkinson-style range
f["gk"] = (c / d.open - 1).mul(100)
f["lasthr_ret"] = f.ret * 0                                # placeholder replaced below
for n in (3, 5, 10, 20, 60):
    f[f"a{n}"] = f.absr.rolling(n).mean(); f[f"pk{n}"] = f.pk.rolling(n).mean(); f[f"rv{n}"] = d.rv5m.rolling(n).mean()
f["rv1"] = d.rv5m; f["rv_lasthr"] = d.rv5m_lasthr; f["rv_first"] = d.rv5m_first
f["gap5"] = f.absgap.rolling(5).mean(); f["gap20"] = f.absgap.rolling(20).mean()
f["vix"] = d.vix; f["vixd"] = d.vix / np.sqrt(252) * 0.8    # VIX-implied mean |daily move| %
f["vix_chg"] = d.vix.pct_change() * 100; f["vix_rel20"] = d.vix / d.vix.rolling(20).mean()
f["mom5"] = (c / c.shift(5) - 1) * 100; f["mom20"] = (c / c.shift(20) - 1) * 100
f["ma20"] = (c / c.rolling(20).mean() - 1) * 100; f["ma50"] = (c / c.rolling(50).mean() - 1) * 100
lh = m5[m5.t >= "14:25"].groupby("date").agg(o=("open", "first"), c=("close", "last")); f["lasthr_ret"] = (lh.c / lh.o - 1) * 100
f["dow_next"] = pd.to_datetime(f.index).dayofweek.map(lambda x: (x + 1) % 5 if x < 4 else 0)
nxt = d.index.to_series().shift(-1); f["next_date"] = nxt
f["y_abs"] = f.absr.shift(-1); f["y_ret"] = f.ret.shift(-1)
f["gap_days"] = (pd.to_datetime(nxt) - pd.to_datetime(f.index)).dt.days
f = f[f.index >= "2021-03-01"].dropna(subset=["a60", "rv60", "vix"]).copy()
f = f[f.index < d.index[-1]]
HAR = ["a3", "a5", "a20", "rv1", "rv5", "rv20", "vixd", "pk5", "absgap", "gap5", "rv_lasthr", "rv_first", "vix_rel20", "gap_days"]
BLOCKS = [("2023-01-01", "2023-07-01"), ("2023-07-01", "2024-01-01"), ("2024-01-01", "2024-07-01"), ("2024-07-01", "2025-01-01"), ("2025-01-01", "2025-07-01"), ("2025-07-01", "2026-01-01"), ("2026-01-01", "2027-01-01")]
def wf(feats, target, mk, transform=None):
    out = pd.Series(np.nan, index=f.index)
    for a, b in BLOCKS:
        tr = f[f.next_date < a].dropna(subset=feats + [target]); te = f[(f.index >= a) & (f.index < b)]
        if len(te) == 0: continue
        y = tr[target] if transform is None else transform(tr[target])
        mdl = mk().fit(tr[feats], y); p = mdl.predict(te[feats].fillna(tr[feats].median()))
        out.loc[te.index] = p
    return out
mk_ols = lambda: make_pipeline(StandardScaler(), RidgeCV(alphas=np.logspace(-1, 3, 12)))
mk_gbm = lambda: GradientBoostingRegressor(n_estimators=150, max_depth=2, learning_rate=0.04, subsample=0.7, min_samples_leaf=30, random_state=0)
f["f_vix"] = f.vixd
f["f_har"] = wf(["a3", "a5", "a20", "rv1", "rv5", "rv20"], "y_abs", mk_ols)
f["f_harvix"] = wf(HAR, "y_abs", mk_ols)
f["f_gbm"] = wf(HAR + ["mom5", "ma20", "vix"], "y_abs", mk_gbm)
O = f[f.index >= BLOCKS[0][0]].dropna(subset=["y_abs", "f_harvix", "f_gbm"]).copy()
print(f"OOS days: {len(O)} ({O.index[0]}..{O.index[-1]}); actual mean |next-day move| = {O.y_abs.mean():.3f}%")
rows = []
for nm in ("f_vix", "f_har", "f_harvix", "f_gbm"):
    e = O.y_abs - O[nm]
    rows.append(dict(forecast=nm, mean_fc=O[nm].mean(), corr=O[[nm, "y_abs"]].corr().iloc[0, 1], spearman=O[[nm, "y_abs"]].corr(method="spearman").iloc[0, 1],
                     MAE=e.abs().mean(), bias=-e.mean(), R2=1 - (e ** 2).sum() / ((O.y_abs - O.y_abs.mean()) ** 2).sum()))
print(pd.DataFrame(rows).round(3).to_string(index=False))
print("\nOOS yearly correlation of forecast with actual |next move|")
O["yr"] = O.index.str[:4]
print(O.groupby("yr").apply(lambda g: pd.Series({nm: g[[nm, "y_abs"]].corr().iloc[0, 1] for nm in ("f_vix", "f_har", "f_harvix", "f_gbm")}) ).round(3))
f.to_csv(os.path.join(R, "range_daily.csv"), float_format="%.5f")
