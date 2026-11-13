"""Define strategy families and run them.

Usage: python3 scripts/09_run_lab.py [START] [END] [OUT_PREFIX]
default: 2025-09-01 .. end of data, results/manual/lab_*
"""
import os, sys, importlib
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
lab_mod = importlib.import_module("08_strategy_lab")
Lab, Leg, Position, stats = lab_mod.Lab, lab_mod.Leg, lab_mod.Position, lab_mod.stats
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAST2 = {1, 2}


# ------------------------------------------------------------------ filters
def f_vrp(th):
    """trade only when the ATM straddle (implied move to expiry) is rich vs recent realised moves."""
    def f(L, d, e, n):
        a = L.atm(d, e)
        if a is None:
            return False
        rv = L.realised(d, 10)
        return (a[1] + a[2]) / (rv * np.sqrt(max(n, 1))) >= th
    return f


def f_vrp_max(th):
    def f(L, d, e, n):
        a = L.atm(d, e)
        if a is None:
            return False
        rv = L.realised(d, 10)
        return (a[1] + a[2]) / (rv * np.sqrt(max(n, 1))) < th
    return f


def f_prevmove(x):
    def f(L, d, e, n):
        i = L.allidx.index(d)
        return abs(L.idx.close.iloc[i] - L.idx.close.iloc[i - 1]) <= x
    return f


def f_rv(x, n=5):
    return lambda L, d, e, n_: L.realised(d, n) <= x


def f_not_weekday(*wds):
    return lambda L, d, e, n: pd.Timestamp(d).dayofweek not in wds


# ------------------------------------------------------------------ builders
def strangle(target=30, dtes=None, exit="next_close", field="close", include_today=False, otm=False,
             wing=None, width=None, stop=None, legs=("CE", "PE"), filt=None, calendar=False, band=None):
    def s(L, i):
        d = L.days[i]
        e = L.expiry(d, 0, include_today)
        if e is None:
            return None
        n = L.dte(d, e)
        if dtes is not None and n not in dtes:
            return None
        if filt is not None and not all(f(L, d, e, n) for f in (filt if isinstance(filt, (list, tuple)) else [filt])):
            return None
        spot = L.spot_open[d] if field == "open" else L.spot[d]
        out = []
        for o in legs:
            kw = dict(lo=target - band, hi=target + band) if band else {}
            r = L.by_price(d, e, o, target, field, otm_of=spot if otm else None, **kw)
            if r is None:
                return None
            out.append(Leg(e, o, r[0], -1, r[1]))
            if wing is not None:
                w = L.by_price(d, e, o, wing, field, otm_of=r[0])
                if w is None:
                    return None
                out.append(Leg(e, o, w[0], +1, w[1]))
            if width is not None:
                w = L.by_strike(d, e, o, r[0] + width if o == "CE" else r[0] - width, field)
                if w is None or w[0] == r[0]:
                    return None
                out.append(Leg(e, o, w[0], +1, w[1]))
            if calendar:
                e2 = L.expiry(d, 1, include_today)
                c2 = L.q(d, e2, o, r[0]) if e2 else None
                if c2 is None or c2["contracts"] <= 0:
                    return None
                out.append(Leg(e2, o, r[0], +1, c2["close"]))
        return Position(out, exit=exit, stop=stop)
    return s


def straddle(dtes=None, exit="next_close", filt=None):
    def s(L, i):
        d = L.days[i]
        e = L.expiry(d)
        if e is None:
            return None
        n = L.dte(d, e)
        if dtes is not None and n not in dtes:
            return None
        if filt is not None and not filt(L, d, e, n):
            return None
        a = L.atm(d, e)
        if a is None:
            return None
        return Position([Leg(e, "CE", a[0], -1, a[1]), Leg(e, "PE", a[0], -1, a[2])], exit=exit)
    return s


def adaptive(mult, dtes=None, exit="next_close", filt=None):
    """strikes placed mult x (ATM straddle price) away from spot: distance scales with implied volatility."""
    def s(L, i):
        d = L.days[i]
        e = L.expiry(d)
        if e is None:
            return None
        n = L.dte(d, e)
        if dtes is not None and n not in dtes:
            return None
        if filt is not None and not filt(L, d, e, n):
            return None
        a = L.atm(d, e)
        if a is None:
            return None
        S, spot = a[1] + a[2], L.spot[d]
        ce = L.by_strike(d, e, "CE", spot + mult * S)
        pe = L.by_strike(d, e, "PE", spot - mult * S)
        if ce is None or pe is None:
            return None
        return Position([Leg(e, "CE", ce[0], -1, ce[1]), Leg(e, "PE", pe[0], -1, pe[1])], exit=exit)
    return s


def oi_walls(dtes=None, exit="next_close"):
    """sell the call strike with the highest call OI above spot and the put strike with highest put OI below spot."""
    def s(L, i):
        d = L.days[i]
        e = L.expiry(d)
        if e is None:
            return None
        n = L.dte(d, e)
        if dtes is not None and n not in dtes:
            return None
        spot, legs = L.spot[d], []
        for o in ("CE", "PE"):
            r = L.traded(d, e, o, "close", otm_of=spot)
            if r is None:
                return None
            c, ok = r
            if not ok.any():
                return None
            ii = np.where(ok)[0]
            j = ii[np.argmax(c["oi"][ii])]
            legs.append(Leg(e, o, c["strike"][j], -1, c["close"][j]))
        return Position(legs, exit=exit)
    return s


def trend_leg(target=30, dtes=LAST2, lookback=5, with_trend=True):
    """one leg only: sell the put in an up-trend (call in a down-trend), or the opposite."""
    def s(L, i):
        d = L.days[i]
        e = L.expiry(d)
        if e is None or L.dte(d, e) not in dtes:
            return None
        j = L.allidx.index(d)
        up = L.idx.close.iloc[j] > L.idx.close.iloc[j - lookback]
        o = ("PE" if up else "CE") if with_trend else ("CE" if up else "PE")
        r = L.by_price(d, e, o, target)
        if r is None:
            return None
        return Position([Leg(e, o, r[0], -1, r[1])])
    return s


def strategies():
    S = []
    add = lambda sid, fam, name, fn, desc: S.append((sid, fam, name, fn, desc))
    # A. baselines
    add("A1", "Baseline", "₹30 strangle, every day", strangle(30), "Your original: nearest ₹30 call + put every day, overnight.")
    add("A2", "Baseline", "₹30 strangle, last 2 days", strangle(30, LAST2), "Best from the premium study: only 1–2 trading days before expiry.")
    add("A3", "Baseline", "₹30 strangle, day before expiry only", strangle(30, {1}), "Only the session before expiry, bought back at the expiry-day close.")
    # B. hold to expiry
    for k in (2, 3, 5):
        for p in (30, 50):
            add(f"B{k}_{p}", "Hold to expiry", f"₹{p} strangle sold {k} days out, held to expiry", strangle(p, {k}, exit="expiry_close"),
                f"Sell nearest ₹{p} call + put {k} trading days before expiry; buy back at the expiry-day close.")
    # C. ATM straddle
    add("C1", "ATM straddle", "ATM straddle, day before expiry", straddle({1}), "Sell the at-the-money call + put the day before expiry.")
    add("C2", "ATM straddle", "ATM straddle, last 2 days", straddle(LAST2), "ATM straddle, 1–2 days before expiry, overnight.")
    add("C3", "ATM straddle", "ATM straddle, every day", straddle(), "ATM straddle every day, overnight.")
    add("C4", "ATM straddle", "ATM straddle sold 2 days out, held to expiry", straddle({2}, exit="expiry_close"), "Two nights to expiry.")
    # D. volatility-adaptive strikes
    for m in (0.75, 1.0, 1.25, 1.5):
        add(f"D{m}", "Vol-adaptive strikes", f"Strikes {m}× straddle away, last 2 days", adaptive(m, LAST2),
            f"Strikes placed {m} × the ATM straddle price away from spot, so distance widens when volatility is high.")
    add("D1.0all", "Vol-adaptive strikes", "Strikes 1× straddle away, every day", adaptive(1.0), "Same, every day.")
    # E. defined risk
    add("E1", "Hedged (iron condor)", "₹30 strangle + ₹5 wings, last 2 days", strangle(30, LAST2, wing=5), "Buy ~₹5 options further out on both sides as crash protection.")
    add("E2", "Hedged (iron condor)", "₹30 strangle + ₹2 wings, last 2 days", strangle(30, LAST2, wing=2), "Cheaper ~₹2 wings.")
    add("E3", "Hedged (iron condor)", "₹30 strangle + wings 200 pts out, last 2 days", strangle(30, LAST2, width=200), "Wings a fixed 200 points beyond each short strike.")
    add("E4", "Hedged (iron condor)", "₹30 strangle + wings 100 pts out, last 2 days", strangle(30, LAST2, width=100), "Tighter 100-point wings.")
    add("E5", "Hedged (iron condor)", "₹30 strangle + ₹5 wings, every day", strangle(30, wing=5), "₹5 wings, every day.")
    add("E6", "Hedged (calendar)", "₹30 strangle hedged with next-week same strikes, last 2 days", strangle(30, LAST2, calendar=True),
        "Sell this week's ₹30 strikes, buy the same strikes in next week's expiry.")
    # F. filters on the best baseline
    for th in (0.8, 1.0, 1.2):
        add(f"F_vrp{th}", "Filters", f"₹30 last 2 days, only when implied ≥ {th}× realised", strangle(30, LAST2, filt=f_vrp(th)),
            f"Skip days when the ATM straddle is cheap relative to the last 10 days' actual moves (ratio < {th}).")
    add("F_vrplow", "Filters", "₹30 last 2 days, only when implied < 1× realised", strangle(30, LAST2, filt=f_vrp_max(1.0)), "The opposite days, for comparison.")
    for x in (150, 250):
        add(f"F_prev{x}", "Filters", f"₹30 last 2 days, skip after a {x}+ pt day", strangle(30, LAST2, filt=f_prevmove(x)), f"No entry if today's Nifty move exceeded {x} points.")
    add("F_rv", "Filters", "₹30 last 2 days, skip when 5-day avg move > 150", strangle(30, LAST2, filt=f_rv(150)), "No entry in high-volatility weeks.")
    add("F_nofri", "Filters", "₹30 day before expiry + Friday skipped", strangle(30, LAST2, filt=f_not_weekday(4)), "Last 2 days but no Friday (weekend) entries.")
    # G. intraday (enter at the open, exit at the same day's close)
    add("G1", "Intraday (open → close)", "₹30 strangle at open, expiry day", strangle(30, {0}, exit="same_close", field="open", include_today=True),
        "Sell at the expiry-day opening price, buy back at that day's close.")
    add("G2", "Intraday (open → close)", "₹30 strangle at open, day before expiry", strangle(30, {1}, exit="same_close", field="open"), "Same, day before expiry.")
    add("G3", "Intraday (open → close)", "₹30 strangle at open, every day", strangle(30, exit="same_close", field="open"), "Same, every day (nearest expiry after today).")
    add("G4", "Intraday (open → close)", "₹15 strangle at open, expiry day", strangle(15, {0}, exit="same_close", field="open", include_today=True), "Cheaper strikes on expiry day.")
    add("G5", "Intraday (open → close)", "₹50 strangle at open, expiry day", strangle(50, {0}, exit="same_close", field="open", include_today=True), "Richer strikes on expiry day.")
    # H. OI walls
    add("H1", "OI-based strikes", "Highest-OI strikes, last 2 days", oi_walls(LAST2), "Sell at the call/put strikes with the most open interest (support/resistance).")
    add("H2", "OI-based strikes", "Highest-OI strikes, every day", oi_walls(), "Same, every day.")
    # I. one side only / trend
    add("I1", "One side / trend", "₹30 call only, last 2 days", strangle(30, LAST2, legs=("CE",)), "Only the call leg.")
    add("I2", "One side / trend", "₹30 put only, last 2 days", strangle(30, LAST2, legs=("PE",)), "Only the put leg.")
    add("I3", "One side / trend", "Sell with trend (5-day), last 2 days", trend_leg(with_trend=True), "Up-trend: sell put only; down-trend: sell call only.")
    add("I4", "One side / trend", "Sell against trend (5-day), last 2 days", trend_leg(with_trend=False), "Up-trend: sell call only; down-trend: sell put only.")
    # J. stops
    add("J1", "Stop-loss", "₹30 last 2 days + 3× stop", strangle(30, LAST2, stop=3), "Exit a leg if it trades at 3× entry (fill at the stop, or the open if it gapped past).")
    add("J2", "Stop-loss", "₹30 held 2 days to expiry + 3× stop", strangle(30, {2}, exit="expiry_close", stop=3), "Two-night hold with a 3× stop.")
    add("J3", "Stop-loss", "₹50 held 5 days to expiry + 2× stop", strangle(50, {5}, exit="expiry_close", stop=2), "Full-week hold with a 2× stop.")
    return S


def main():
    start = sys.argv[1] if len(sys.argv) > 1 else "2025-09-01"
    end = sys.argv[2] if len(sys.argv) > 2 else None
    prefix = sys.argv[3] if len(sys.argv) > 3 else "lab"
    out = os.path.join(ROOT, "results", "manual")
    os.makedirs(out, exist_ok=True)
    L = Lab(start=str(pd.Timestamp(start) - pd.Timedelta(days=45))[:10], end=end)
    split = "2026-04-01" if start >= "2025-09-01" else str(pd.Timestamp(start) + (pd.Timestamp(end or L.days[-1]) - pd.Timestamp(start)) / 2)[:10]
    summ, trades = [], []
    for sid, fam, name, fn, desc in strategies():
        t = L.run(fn, start, end, name=sid)
        st = stats(t, split) if len(t) else {"trades": 0}
        summ.append(dict(sid=sid, family=fam, name=name, description=desc, **st))
        if len(t):
            trades.append(t)
        print(f"{sid:9s} {st.get('trades',0):4d} {st.get('total',0):9.1f}  {name}", flush=True)
    pd.DataFrame(summ).to_csv(os.path.join(out, f"{prefix}_summary.csv"), index=False, float_format="%.2f")
    pd.concat(trades).to_csv(os.path.join(out, f"{prefix}_trades.csv"), index=False, float_format="%.2f")


if __name__ == "__main__":
    main()
