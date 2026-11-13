"""Build dashboard.html (single self-contained file, works offline) from results/."""
import json, os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "results")
REF_LOT = 65


def clean(v):
    if isinstance(v, (float, np.floating)):
        return None if np.isnan(v) else round(float(v), 3)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.bool_,)):
        return bool(v)
    return v


def records(df):
    return [{k: clean(v) for k, v in r.items()} for r in df.to_dict("records")]


def main():
    summ = pd.read_csv(os.path.join(R, "strategy_summary.csv"))
    trades = pd.read_csv(os.path.join(R, "all_trades.csv.gz"), parse_dates=["date"])
    meta = json.load(open(os.path.join(R, "meta.json")))
    years = sorted(int(c[1:]) for c in summ.columns if c.startswith("y") and c[1:].isdigit())
    dates = sorted(trades.date.unique())
    dkey = {d: i for i, d in enumerate(dates)}
    daily = {}
    for sid, g in trades.groupby("sid"):
        arr = np.zeros(len(dates))
        s = g.groupby("date").net.sum()
        for d, v in s.items():
            arr[dkey[d]] = v
        daily[sid] = [round(x, 1) for x in arr]
    findings_path = os.path.join(R, "findings.json")
    findings = json.load(open(findings_path)) if os.path.exists(findings_path) else {}
    data = {
        "meta": meta, "refLot": REF_LOT, "years": years,
        "dates": [pd.Timestamp(d).strftime("%Y-%m-%d") for d in dates],
        "strategies": records(summ), "daily": daily,
        "byDte": records(pd.read_csv(os.path.join(R, "user_by_dte.csv"))),
        "byMove": records(pd.read_csv(os.path.join(R, "user_by_move.csv"))),
        "grid": records(pd.read_csv(os.path.join(R, "robustness_grid.csv"))),
        "cost": records(pd.read_csv(os.path.join(R, "cost_sensitivity.csv"))),
        "dist": records(pd.read_csv(os.path.join(R, "move_distribution.csv"))),
        "findings": findings,
    }
    tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard_template.html")).read()
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    body = tpl.replace("/*__DATA__*/null", payload)
    # dashboard.html: standalone file to double-click (full document)
    full = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
            '</head>\n<body>\n' + body + '\n</body>\n</html>\n')
    out = os.path.join(ROOT, "dashboard.html")
    with open(out, "w") as f:
        f.write(full)
    # results/dashboard_page.html: same page without the document wrapper, for publishing
    with open(os.path.join(R, "dashboard_page.html"), "w") as f:
        f.write(body)
    print(f"wrote {out} ({len(full)/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
