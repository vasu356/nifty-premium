"""Merge daily downloads into clean analysis tables.

Writes:
  data/nifty_options_all.csv.gz  every Nifty option row (date, expiry, strike, opt, OHLC, settle, contracts, oi)
  data/nifty_index.csv           Nifty 50 daily OHLC (2020 onwards)
  data/lot_sizes.csv             lot size per trading day (from the near-month future)
"""
import glob, os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")


def main():
    files = sorted(glob.glob(os.path.join(D, "fo_daily", "*.csv.gz")))
    fo = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    fo["date"] = pd.to_datetime(fo["date"])
    fo["expiry"] = pd.to_datetime(fo["expiry"])
    for c in ["open", "high", "low", "close", "settle", "turnover_rs", "strike"]:
        fo[c] = pd.to_numeric(fo[c], errors="coerce")

    # ---- lot size: from the published lot (UDiFF) else from near-month future turnover
    fut = fo[fo.instrument == "FUTIDX"].sort_values(["date", "expiry"]).groupby("date").first()
    implied = fut.turnover_rs / (fut.contracts * (fut.high + fut.low) / 2)
    lot = pd.to_numeric(fut["lot"], errors="coerce")
    lot = lot.fillna(implied)
    choices = np.array([25, 50, 65, 75])
    lot = lot.apply(lambda x: choices[np.abs(choices - x).argmin()] if pd.notna(x) else np.nan)
    lot = lot.ffill().bfill().astype(int)
    lot.rename("lot").to_csv(os.path.join(D, "lot_sizes.csv"), date_format="%Y-%m-%d")
    changes = lot[lot.diff().fillna(1) != 0]
    print("lot size changes:\n", changes.to_string())

    # ---- options table
    op = fo[fo.instrument == "OPTIDX"].drop(columns=["instrument", "turnover_rs", "lot"])
    op = op[op.opt.isin(["CE", "PE"])]
    op = op.drop_duplicates(["date", "expiry", "strike", "opt"])
    op["contracts"] = op.contracts.fillna(0).astype(np.int64)
    op = op.sort_values(["date", "expiry", "opt", "strike"])
    op.to_csv(os.path.join(D, "nifty_options_all.csv.gz"), index=False,
              date_format="%Y-%m-%d", compression="gzip")
    print(f"options: {len(op):,} rows, {op.date.nunique()} days, {op.expiry.nunique()} expiries")

    # ---- index
    idx = pd.concat((pd.read_csv(f, header=None, names=["date", "open", "high", "low", "close"])
                     for f in sorted(glob.glob(os.path.join(D, "index_daily", "*.csv")))))
    idx = idx.sort_values("date")
    idx.to_csv(os.path.join(D, "nifty_index.csv"), index=False)
    print(f"index: {len(idx)} days {idx.date.min()} .. {idx.date.max()}")
    missing = set(op.date.dt.strftime("%Y-%m-%d")) - set(idx.date)
    print("option days with no index row:", sorted(missing))


if __name__ == "__main__":
    main()
