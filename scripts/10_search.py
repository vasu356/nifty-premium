"""Wide strategy search on two periods, after charges.

Charges: ₹65 per option leg round trip at a 65-unit lot = 1 point per leg
(so the usual 2-leg trade pays 2 points = ₹130).

Periods: OLD = 2021-01-04 .. 2025-08-29 (Thursday expiries)
         NEW = 2025-09-01 .. 2026-11-12 (Tuesday expiries)
Writes results/manual/search_results.csv and search_trades_<id>.csv for finalists.
"""
import os, sys, importlib, itertools, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
Lab, Leg, Position = labm.Lab, labm.Leg, labm.Position
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "manual")
OLD = ("2021-01-04", "2025-08-29")
NEW = ("2025-09-01", None)
CHARGE_PER_LEG = 1.0


# ------------------------------------------------------------ filters (use only data known at entry)
def prev_move(L, d):
    j = L.allidx.index(d)
    return L.idx.close.iloc[j] - L.idx.close.iloc[j - 1]


def ret_n(L, d, n):
    j = L.allidx.index(d)
    return L.idx.close.iloc[j] - L.idx.close.iloc[j - n]


def make_filter(kind, x):
    if kind is None:
        return None
    if kind == "skip_prev_move":          # skip if today's |move| > x points
        return lambda L, d, e, n, S: abs(prev_move(L, d)) <= x
    if kind == "skip_rich":               # skip if straddle/spot > x (very high implied vol)
        return lambda L, d, e, n, S: S / L.spot[d] <= x
    if kind == "skip_cheap":              # skip if straddle/spot < x (very low implied vol)
        return lambda L, d, e, n, S: S / L.spot[d] >= x
    if kind == "skip_after_big_week":     # skip if 5-day |move| > x
        return lambda L, d, e, n, S: abs(ret_n(L, d, 5)) <= x
    if kind == "weekday_not":             # skip a weekday (0=Mon..4=Fri)
        return lambda L, d, e, n, S: pd.Timestamp(d).dayofweek != x
    raise ValueError(kind)


# ------------------------------------------------------------ the general builder
def builder(mc=1.0, mp=1.0, dtes=frozenset({1, 2}), rank=0, exit="next_close", max_days=None,
            tp=None, cs=None, wing=None, filt=None, shift=0.0, shift_n=5, legs=("CE", "PE")):
    """Sell CE at spot + mc*S and PE at spot - mp*S where S = ATM straddle of the chosen expiry.
    rank: 0 = nearest expiry after today, 1 = the one after. dtes: allowed trading days to that expiry.
    shift: move the centre by shift * (n-day Nifty change) (positive = with trend).
    wing: buy protection at spot +/- wing*S (iron condor)."""
    def s(L, i):
        d = L.days[i]
        e = L.expiry(d, rank)
        if e is None:
            return None
        n = L.dte(d, e)
        if dtes is not None and n not in dtes:
            return None
        a = L.atm(d, e)
        if a is None:
            return None
        S = a[1] + a[2]
        if filt is not None and not filt(L, d, e, n, S):
            return None
        spot = L.spot[d]
        centre = spot + (shift * ret_n(L, d, shift_n) if shift else 0.0)
        out = []
        for o in legs:
            m = mc if o == "CE" else mp
            tgt = centre + m * S if o == "CE" else centre - m * S
            r = L.by_strike(d, e, o, tgt)
            if r is None:
                return None
            out.append(Leg(e, o, r[0], -1, r[1]))
            if wing is not None:
                wt = spot + wing * S if o == "CE" else spot - wing * S
                w = L.by_strike(d, e, o, wt)
                if w is None or w[0] == r[0]:
                    return None
                out.append(Leg(e, o, w[0], +1, w[1]))
        return Position(out, exit=exit, max_days=max_days, take_profit=tp, close_stop=cs)
    return s


def evaluate(t, start, end):
    if t is None or len(t) == 0:
        return dict(n=0)
    t = t.copy()
    t["net"] = t.total - CHARGE_PER_LEG * t.legs.str.count("/").add(1)
    eq = t.net.cumsum()
    dd = (eq - eq.cummax()).min()
    m = t.groupby(t.sell.str[:7]).net.sum()
    y = t.groupby(t.sell.str[:4]).net.sum()
    return dict(n=len(t), net=t.net.sum(), avg=t.net.mean(), win=(t.net > 0).mean(), worst=t.net.min(),
                dd=dd, rdd=t.net.sum() / abs(dd) if dd < 0 else np.inf,
                mpos=(m > 0).mean(), ypos=f"{int((y > 0).sum())}/{len(y)}", prem=t.short_prem.mean())


def configs():
    C = []
    add = lambda fam, label, **kw: C.append((fam, label, kw))
    mults = (0.5, 0.6, 0.75, 0.9, 1.0, 1.25, 1.5, 2.0)
    dsets = {"1": {1}, "2": {2}, "1-2": {1, 2}, "1-3": {1, 2, 3}, "3": {3}, "4": {4}, "5": {5}, "all": None}
    # 1. timing x distance, overnight, nearest expiry
    for m, (dl, ds) in itertools.product(mults, dsets.items()):
        add("1 timing×distance", f"{m}× · sold {dl} days out · overnight", mc=m, mp=m, dtes=ds)
    # 2. next-week expiry instead of nearest (overnight)
    for m in (0.5, 0.75, 1.0, 1.25):
        for dl, ds in {"6-7": {6, 7}, "all": None}.items():
            add("2 next-week expiry", f"{m}× · next-week expiry · {dl} days out · overnight", mc=m, mp=m, dtes=ds, rank=1)
    # 3. holding longer: sell k days out, hold to expiry, with/without take-profit and close-stops
    for m, k in itertools.product((0.75, 1.0, 1.25, 1.5, 2.0), (2, 3, 5)):
        add("3 hold to expiry", f"{m}× · sold {k} days out · hold to expiry", mc=m, mp=m, dtes={k}, exit="expiry_close")
        for tp in (0.5, 0.7):
            add("3 hold + take-profit", f"{m}× · sold {k} days out · hold, exit at {int(tp*100)}% captured", mc=m, mp=m, dtes={k}, exit="expiry_close", tp=tp)
        for cs in (2.0, 3.0):
            add("3 hold + close-stop", f"{m}× · sold {k} days out · hold, stop at {cs}× credit (at close)", mc=m, mp=m, dtes={k}, exit="expiry_close", cs=cs)
    # 4. asymmetric call/put distance (last 2 days)
    for mc, mp in itertools.product((0.6, 0.75, 1.0, 1.25), (0.6, 0.75, 1.0, 1.25, 1.5)):
        add("4 asymmetric", f"call {mc}× / put {mp}× · last 2 days", mc=mc, mp=mp)
    # 5. filters on the base (1.0x, last 2 days)
    for kind, xs in {"skip_prev_move": (150, 200, 250, 300, 400), "skip_rich": (0.012, 0.015, 0.02),
                     "skip_cheap": (0.004, 0.005, 0.006), "skip_after_big_week": (400, 600, 800), "weekday_not": (0, 4)}.items():
        for x in xs:
            for m in (0.75, 1.0):
                add("5 filters", f"{m}× · last 2 days · {kind} {x}", mc=m, mp=m, filt=make_filter(kind, x))
    # 6. trend-shifted centre
    for sh, n, m in itertools.product((0.25, 0.5, -0.25), (3, 5), (0.75, 1.0)):
        add("6 trend shift", f"{m}× · last 2 days · centre shifted {sh}× {n}-day move", mc=m, mp=m, shift=sh, shift_n=n)
    # 7. wings
    for m, w in itertools.product((0.6, 0.75, 1.0), (1.75, 2.0, 2.5, 3.0)):
        add("7 iron condor", f"{m}× short / {w}× wings · last 2 days", mc=m, mp=m, wing=w)
    return C


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    L = Lab(start="2020-11-15")
    print(f"loaded {time.time()-t0:.0f}s", flush=True)
    rows = []
    C = configs()
    for k, (fam, label, kw) in enumerate(C):
        fn = builder(**kw)
        t = L.run(fn, OLD[0])
        old = evaluate(t[t.sell <= OLD[1]], *OLD) if len(t) else {}
        new = evaluate(t[t.sell >= NEW[0]], *NEW) if len(t) else {}
        rows.append(dict(id=k, family=fam, label=label, **{f"old_{a}": b for a, b in old.items()}, **{f"new_{a}": b for a, b in new.items()}))
        if k % 25 == 0:
            print(k, len(C), f"{time.time()-t0:.0f}s", flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "search_results.csv"), index=False, float_format="%.4f")
    print("done", time.time() - t0)


if __name__ == "__main__":
    main()
