"""Run every strategy and write results/ CSVs used by the dashboard.

Edit STRATEGIES below to add or change strategies, then re-run this script and
05_make_dashboard.py.
"""
import json, os, sys, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import importlib
bt = importlib.import_module("03_backtest")
Strategy, Costs = bt.Strategy, bt.Costs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = os.path.join(ROOT, "results")
os.makedirs(R, exist_ok=True)
LAST2 = {1, 2}


def S(*a, **k):
    return Strategy(*a, **k)


STRATEGIES = [
    # --- the user's strategy and close variants
    S("U1", "Your strategy: sell ₹30±5 call + put daily, buy back next day", "Your strategy",
      target=30, band=5, user=True,
      description="Every day at close, sell the nearest-expiry OTM call and put trading closest to ₹30 (₹25–35); buy both back at the next day's close."),
    S("U2", "₹30 ±3 band", "Your strategy", target=30, band=3, description="Tighter premium band."),
    S("U3", "₹30 ±10 band", "Your strategy", target=30, band=10, description="Wider premium band (fewer skipped days)."),
    S("U4", "₹30, call only", "Your strategy", target=30, band=5, legs=("CE",), description="Only the call leg."),
    S("U5", "₹30, put only", "Your strategy", target=30, band=5, legs=("PE",), description="Only the put leg."),
    S("U6", "₹30, skip day after a 150+ pt move", "Your strategy", target=30, band=5, skip_after_move=150,
      description="Same, but no entry if today's close-to-close move exceeded 150 pts."),
]
# --- premium level, every day
for p in [10, 15, 20, 40, 50, 75, 100]:
    STRATEGIES.append(S(f"P{p}", f"₹{p} strangle, every day", "Premium level (daily)", target=p, band=max(2, p / 6),
                        description=f"Daily overnight strangle at ~₹{p} per leg."))
STRATEGIES += [
    S("A1", "ATM straddle, every day", "Premium level (daily)", select="atm", description="Sell the ATM call + put daily, overnight."),
    S("D200", "200 pts OTM strangle, every day", "Distance (daily)", select="distance", distance=200, description="Strikes ≥200 pts OTM."),
    S("D300", "300 pts OTM strangle, every day", "Distance (daily)", select="distance", distance=300, description="Strikes ≥300 pts OTM."),
    S("D500", "500 pts OTM strangle, every day", "Distance (daily)", select="distance", distance=500, description="Strikes ≥500 pts OTM."),
]
# --- days-to-expiry filters with ₹30
for n in [1, 2, 3, 4, 5]:
    STRATEGIES.append(S(f"T{n}", f"₹30, only {n} day{'s' if n > 1 else ''} before expiry", "Days to expiry (₹30)",
                        target=30, band=5, dte={n},
                        description=f"Your strategy, entered only when expiry is {n} trading day{'s' if n > 1 else ''} away."))
STRATEGIES.append(S("T345", "₹30, 3+ days before expiry", "Days to expiry (₹30)", target=30, band=5, dte={3, 4, 5, 6, 7},
                    description="Your strategy, only when expiry is 3 or more trading days away."))
# --- last 2 trading days
for p in [10, 20, 30, 50, 75, 100]:
    STRATEGIES.append(S(f"L{p}", f"Last 2 days, ₹{p} strangle", "Last 2 days before expiry",
                        target=p, band=max(2, p / 6), dte=LAST2,
                        description=f"Overnight ~₹{p} strangle, only on the 2 trading days before expiry."))
STRATEGIES += [
    S("LCE", "Last 2 days, ₹30 call only", "Last 2 days before expiry", target=30, band=5, dte=LAST2, legs=("CE",),
      description="Only the call leg, last 2 trading days before expiry."),
    S("LPE", "Last 2 days, ₹30 put only", "Last 2 days before expiry", target=30, band=5, dte=LAST2, legs=("PE",),
      description="Only the put leg, last 2 trading days before expiry."),
    S("LSK", "Last 2 days ₹30, skip after 150+ pt move", "Last 2 days before expiry", target=30, band=5, dte=LAST2,
      skip_after_move=150, description="Last-2-days ₹30 strangle, no entry after a 150+ pt day."),
    S("T1_50", "Day before expiry only, ₹50", "Last 2 days before expiry", target=50, band=8, dte={1},
      description="Sell a ~₹50 strangle only on the day before expiry; it settles at expiry."),
    S("LATM", "Last 2 days, ATM straddle", "Last 2 days before expiry", select="atm", dte=LAST2,
      description="ATM straddle, only on the 2 trading days before expiry."),
    S("L300", "Last 2 days, 300 pts OTM", "Last 2 days before expiry", select="distance", distance=300, dte=LAST2,
      description="Strikes ≥300 pts OTM, only on the 2 trading days before expiry."),
    S("H2", "Hold to expiry from 2 days out, ₹30", "Hold to expiry", target=30, band=5, dte={2}, hold="expiry",
      description="Sell ₹30 strangle 2 trading days before expiry, hold to settlement."),
    S("H3", "Hold to expiry from 3 days out, ₹30", "Hold to expiry", target=30, band=5, dte={3}, hold="expiry",
      description="Sell ₹30 strangle 3 trading days before expiry, hold to settlement."),
    S("H2_50","Hold to expiry from 2 days out, ₹50", "Hold to expiry", target=50, band=8, dte={2}, hold="expiry",
      description="Sell ₹50 strangle 2 trading days before expiry, hold to settlement."),
    S("W30", "Full week, ₹30, hold to expiry", "Hold to expiry", target=30, band=5, dte={5}, hold="expiry",
      description="Sell ₹30 strangle at the start of the weekly cycle (5 days out) and hold to expiry."),
    S("W50", "Full week, ₹50, hold to expiry", "Hold to expiry", target=50, band=8, dte={5}, hold="expiry",
      description="Sell ₹50 strangle 5 days out and hold to expiry."),
    S("W100", "Full week, ₹100, hold to expiry", "Hold to expiry", target=100, band=15, dte={5}, hold="expiry",
      description="Sell ₹100 strangle 5 days out and hold to expiry."),
    # --- protection
    S("C1", "Your strategy + ₹5 wings (iron condor)", "Hedged / stop-loss", target=30, band=5, wing=5,
      description="Your strategy, plus buy ~₹5 further-OTM call and put as protection."),
    S("C2", "Last 2 days ₹30 + ₹5 wings", "Hedged / stop-loss", target=30, band=5, wing=5, dte=LAST2,
      description="Last-2-days ₹30 strangle hedged with ~₹5 wings."),
    S("C3", "Full week ₹50 + ₹10 wings", "Hedged / stop-loss", target=50, band=8, wing=10, dte={5}, hold="expiry",
      description="Full-week ₹50 iron condor held to expiry."),
    S("SL2", "Your strategy + 2× stop (realistic)", "Hedged / stop-loss", target=30, band=5, stop=2.0,
      description="Exit a leg if it doubles; on a gap the fill is the open price."),
    S("SL15", "Your strategy + 1.5× stop (realistic)", "Hedged / stop-loss", target=30, band=5, stop=1.5,
      description="Exit a leg at +50%; gap fills at open."),
    S("SL2X", "Your strategy + 2× stop (exact fill, unrealistic)", "Hedged / stop-loss", target=30, band=5, stop=2.0,
      exact_stop_fill=True, description="Assumes the stop always fills exactly at 2× — not achievable on gaps."),
    S("WSL", "Full week ₹50 + 2× stop (realistic)", "Hedged / stop-loss", target=50, band=8, dte={5}, hold="expiry", stop=2.0,
      description="Full-week ₹50 strangle with a 2× per-leg stop checked daily."),
    S("LSL", "Last 2 days ₹50 + 2× stop (realistic)", "Hedged / stop-loss", target=50, band=8, dte=LAST2, stop=2.0,
      description="Last-2-days ₹50 strangle with a 2× stop; gap fills at open."),
]


def move_distribution(m):
    s = m.spot
    s = s[s.index >= "2023-01-01"]
    mv = s.diff().dropna()
    edges = np.arange(-700, 701, 50)
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        if lo == -700:
            sel = mv < hi
            label = f"below {hi:+d}"
        elif hi == 700:
            sel = mv >= lo
            label = f"{lo:+d} or more"
        else:
            sel = (mv >= lo) & (mv < hi)
            label = f"{lo:+d} to {hi:+d}"
        rows.append({"range": label, "lo": lo, "hi": hi, "days": int(sel.sum()), "pct": sel.mean()})
    out = pd.DataFrame(rows)
    out["rank"] = out.days.rank(ascending=False, method="min").astype(int)
    absmv = mv.abs()
    within = {f"within_{k}": float((absmv <= k).mean()) for k in [50, 100, 150, 200, 300, 400]}
    return out, within, mv


def main():
    t0 = time.time()
    m = bt.Market()
    print(f"market loaded in {time.time()-t0:.0f}s: {len(m.tdays)} days", flush=True)

    summaries, all_trades = [], []
    for s in STRATEGIES:
        t = bt.run(m, s)
        t.insert(0, "sid", s.sid)
        all_trades.append(t)
        summaries.append(bt.summarize(s, t))
        print(f"{s.sid:6s} trades={len(t):5d} net={t.net.sum() if len(t) else 0:9.0f}  {s.name}", flush=True)
    summ = pd.DataFrame(summaries)
    summ.to_csv(os.path.join(R, "strategy_summary.csv"), index=False, float_format="%.4f")
    trades = pd.concat(all_trades, ignore_index=True)
    trades.to_csv(os.path.join(R, "all_trades.csv.gz"), index=False, float_format="%.2f", compression="gzip")

    # --- breakdowns for the user's strategy
    u = trades[trades.sid == "U1"].copy()
    by_dte = u.groupby("dte").agg(trades=("net", "size"), gross=("gross", "sum"), cost=("cost", "sum"),
                                  net=("net", "sum"), win_rate=("net", lambda x: (x > 0).mean())).reset_index()
    by_dte.to_csv(os.path.join(R, "user_by_dte.csv"), index=False, float_format="%.4f")
    bins = [0, 50, 100, 150, 200, 300, 10_000]
    labels = ["0–50", "50–100", "100–150", "150–200", "200–300", "300+"]
    u["absmove"] = pd.cut(u.move.abs(), bins=bins, labels=labels, right=False)
    by_move = u.groupby("absmove", observed=False).agg(
        trades=("net", "size"), net=("net", "sum"), avg=("net", "mean"),
        win_rate=("net", lambda x: (x > 0).mean())).reset_index()
    by_move.to_csv(os.path.join(R, "user_by_move.csv"), index=False, float_format="%.4f")

    # --- cost sensitivity (user strategy and the last-2-days ₹30 version)
    rows = []
    for sid in ["U1", "L30", "L50"]:
        s = next(x for x in STRATEGIES if x.sid == sid)
        for slip in [0.0, 0.25, 0.5, 1.0, 1.5]:
            for brok in [0.0, 20.0]:
                t = bt.run(m, s, Costs(slip=slip, brokerage=brok))
                rows.append({"sid": sid, "slip": slip, "brokerage": brok, "net": t.net.sum(), "gross": t.gross.sum()})
    pd.DataFrame(rows).to_csv(os.path.join(R, "cost_sensitivity.csv"), index=False, float_format="%.2f")

    # --- robustness grid: premium x DTE filter (net points)
    grid = []
    for p in [10, 20, 30, 40, 50, 75, 100]:
        for label, dte in [("1 day", {1}), ("2 days", {2}), ("Last 2", LAST2), ("3+ days", {3, 4, 5, 6, 7}), ("Every day", None)]:
            s = Strategy("g", "g", "g", target=p, band=max(2, p / 6), dte=dte)
            t = bt.run(m, s)
            yr = t.groupby(t.date.dt.year).net.sum()
            grid.append({"premium": p, "dte": label, "trades": len(t), "net": t.net.sum(),
                         "years_pos": int((yr > 0).sum()), "years": len(yr)})
        print("grid", p, flush=True)
    pd.DataFrame(grid).to_csv(os.path.join(R, "robustness_grid.csv"), index=False, float_format="%.2f")

    # --- probability of daily moves
    dist, within, mv = move_distribution(m)
    dist.to_csv(os.path.join(R, "move_distribution.csv"), index=False, float_format="%.4f")
    meta = {
        "first_day": str(pd.Timestamp(m.tdays[0]).date()), "last_day": str(pd.Timestamp(m.tdays[-1]).date()),
        "trading_days": len(m.tdays), "move_days": int(len(mv)),
        "move_from": str(mv.index.min().date()), **within,
        "lot_changes": {str(k.date()): int(v) for k, v in m.lot[m.lot.diff().fillna(1) != 0].items()},
    }
    with open(os.path.join(R, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)
    print(f"done in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
