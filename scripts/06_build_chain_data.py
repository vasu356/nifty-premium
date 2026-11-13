"""Build compact per-month JSON files for the option-chain viewer.

Writes chain_viewer/data/index.json and chain_viewer/data/YYYY-MM.json.
Prices are stored as integer ticks of 0.05 (so 30.15 -> 603) to keep files small.

Per month file layout:
  {"days": {"2024-07-08": {"spot": [o,h,l,c], "lot": 25,
            "exp": {"2024-07-11": {"k": [strikes...],
                                   "CE": {"o":[..],"h":[..],"l":[..],"c":[..],"s":[..],"ch":[..],"v":[..],"oi":[..],"coi":[..]},
                                   "PE": {...}}}}}}
  v = contracts traded; oi / coi = open interest and its change, in contracts;
  ch = change in close vs the same contract's previous trading day (null if new).
  A strike missing on one side has null in that side's arrays.
"""
import json, os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "chain_viewer", "data")


def ticks(x):
    return None if pd.isna(x) else int(round(x * 20))


def main():
    os.makedirs(OUT, exist_ok=True)
    op = pd.read_csv(os.path.join(ROOT, "data", "nifty_options_all.csv.gz"))
    lot = pd.read_csv(os.path.join(ROOT, "data", "lot_sizes.csv")).set_index("date").lot
    idx = pd.read_csv(os.path.join(ROOT, "data", "nifty_index.csv")).set_index("date")
    op = op.sort_values(["expiry", "strike", "opt", "date"])
    key = ["expiry", "strike", "opt"]
    op["prev_close"] = op.groupby(key).close.shift()
    op["prev_oi"] = op.groupby(key).oi.shift()
    op["lot"] = op.date.map(lot).fillna(75).astype(int)
    op["oi_c"] = (op.oi.fillna(0) / op.lot).round().astype(int)
    op["coi_c"] = ((op.oi.fillna(0) - op.prev_oi) / op.lot).round()
    op["month"] = op.date.str[:7]

    index = {"days": {}, "months": [], "fields": "prices in ticks of 0.05; oi/coi in contracts; v = contracts traded"}
    years = {}
    for month, gm in op.groupby("month"):
        days = {}
        for d, gd in gm.groupby("date"):
            exp_out = {}
            for e, ge in gd.groupby("expiry"):
                strikes = sorted(ge.strike.unique())
                pos = {k: i for i, k in enumerate(strikes)}
                sides = {}
                for side in ("CE", "PE"):
                    gs = ge[ge.opt == side]
                    arr = {f: [None] * len(strikes) for f in ("o", "h", "l", "c", "s", "ch", "v", "oi", "coi")}
                    for r in gs.itertuples(index=False):
                        i = pos[r.strike]
                        traded = r.contracts > 0
                        arr["o"][i] = ticks(r.open) if traded else None
                        arr["h"][i] = ticks(r.high) if traded else None
                        arr["l"][i] = ticks(r.low) if traded else None
                        arr["c"][i] = ticks(r.close)
                        arr["s"][i] = ticks(r.settle)
                        arr["ch"][i] = None if pd.isna(r.prev_close) else ticks(r.close - r.prev_close)
                        arr["v"][i] = int(r.contracts)
                        arr["oi"][i] = int(r.oi_c)
                        arr["coi"][i] = None if pd.isna(r.coi_c) else int(r.coi_c)
                    sides[side] = arr
                exp_out[e] = {"k": [int(k) if float(k).is_integer() else k for k in strikes], **sides}
            sp = idx.loc[d] if d in idx.index else None
            days[d] = {"spot": None if sp is None else [round(float(sp.open), 2), round(float(sp.high), 2), round(float(sp.low), 2), round(float(sp.close), 2)],
                       "lot": int(lot.get(d, 75)), "exp": exp_out}
            index["days"][d] = {"m": month, "e": sorted(exp_out),
                                "spot": days[d]["spot"][3] if days[d]["spot"] else None,
                                "rows": int(len(gd)), "traded": int((gd.contracts > 0).sum())}
        with open(os.path.join(OUT, f"{month}.json"), "w") as f:
            json.dump({"days": days}, f, separators=(",", ":"))
        index["months"].append(month)
        y = month[:4]
        ys = years.setdefault(y, {"days": 0, "rows": 0, "traded": 0, "expiries": set()})
        ys["days"] += gm.date.nunique(); ys["rows"] += len(gm); ys["traded"] += int((gm.contracts > 0).sum())
        ys["expiries"].update(gm.expiry.unique())
        print(month, end=" ", flush=True)
    index["years"] = {y: {**{k: v for k, v in s.items() if k != "expiries"}, "expiries": len(s["expiries"])} for y, s in years.items()}
    index["totals"] = {"days": len(index["days"]), "rows": int(len(op)), "traded": int((op.contracts > 0).sum()),
                       "expiries": int(op.expiry.nunique()), "contracts": int(op[key].drop_duplicates().shape[0]),
                       "first": min(index["days"]), "last": max(index["days"])}
    # first/last day each contract appears, so the history view knows which months to load
    life = op.groupby("expiry").date.agg(["min", "max"])
    index["expiryLife"] = {e: [r["min"], r["max"]] for e, r in life.iterrows()}
    with open(os.path.join(OUT, "index.json"), "w") as f:
        json.dump(index, f, separators=(",", ":"))
    tot = sum(os.path.getsize(os.path.join(OUT, x)) for x in os.listdir(OUT))
    print(f"\n{len(index['months'])} month files, {tot/1e6:.1f} MB total")


if __name__ == "__main__":
    main()
