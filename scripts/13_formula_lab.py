"""Formula lab: many ways to choose the two strikes for the Fri/Mon (1-2 days before expiry) trade.

Rules held fixed: nearest expiry after today, dte in {1,2}, sell at close, buy back next close,
2 points of charges per trade (Rs 130 at a 65 lot). Only the strike choice varies.

Writes results/manual/formula_grid.csv (one row per variant, 4 windows + yearly nets).
"""
import os, sys, importlib, itertools, time
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
Lab, Leg, Position = labm.Lab, labm.Leg, labm.Position
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "manual")
CHARGE = 2.0
WINDOWS = {"P1": ("2021-01-04", "2025-08-29"), "P2": ("2025-09-01", "2099-01-01"),
           "W1": ("2021-01-04", "2023-12-31"), "W2": ("2024-01-01", "2099-01-01")}


def ret_n(L, d, n):
    j = L.allidx.index(d)
    return L.idx.close.iloc[j] - L.idx.close.iloc[j - n]


def fbuilder(unit="S", p=0.0, N=10, mode="dist", kc=0.75, kp=1.0, shift=0.15, shift_n=5, shift_cap=None,
             floor=0.0, minprem=0.0, dtes=frozenset({1, 2}), gamma=1.0, ref=0.0075,
             fixed=None, pct=None, eq=None):
    """unit: 'S' straddle/n**p | 'R' realised mean |daily move| over N days | 'avg' | 'max' (of S/sqrt(n) and R)
    mode: 'dist' (multipliers of unit) | 'fixed' (points) | 'pct' (% of spot) | 'eq' (premium = a*S, b*S)"""
    def s(L, i):
        d = L.days[i]
        e = L.expiry(d)
        if e is None:
            return None
        n = L.dte(d, e)
        if n not in dtes:
            return None
        at = L.atm(d, e)
        if at is None:
            return None
        S = at[1] + at[2]
        spot = L.spot[d]
        if unit == "S":
            U = S / (n ** p)
        else:
            Rr = L.realised(d, N)
            Ui = S / np.sqrt(n)
            U = Rr if unit == "R" else (0.5 * (Ui + Rr) if unit == "avg" else max(Ui, Rr))
        if gamma != 1.0:
            U = U * ((S / spot) / ref) ** (gamma - 1.0)
        tr = shift * ret_n(L, d, shift_n) if shift else 0.0
        if shift_cap is not None and shift:
            tr = float(np.clip(tr, -shift_cap * U, shift_cap * U))
        centre = spot + tr
        if mode == "eq":
            ce = L.by_price(d, e, "CE", eq[0] * S, otm_of=spot)
            pe = L.by_price(d, e, "PE", eq[1] * S, otm_of=spot)
        else:
            if mode == "dist":
                ct, pt = centre + kc * U, centre - kp * U
            elif mode == "fixed":
                ct, pt = centre + fixed[0], centre - fixed[1]
            else:
                ct, pt = centre + pct[0] * spot, centre - pct[1] * spot
            if floor:
                ct, pt = max(ct, spot + floor * U), min(pt, spot - floor * U)
            ce, pe = L.by_strike(d, e, "CE", ct), L.by_strike(d, e, "PE", pt)
        if ce is None or pe is None:
            return None
        if minprem and ce[1] + pe[1] < minprem:
            return None
        return Position([Leg(e, "CE", ce[0], -1, ce[1]), Leg(e, "PE", pe[0], -1, pe[1])], exit="next_close")
    return s


def ev(t):
    if len(t) == 0:
        return dict(n=0)
    eq = t.net.cumsum()
    dd = (eq - eq.cummax()).min()
    m = t.groupby(t.sell.str[:7]).net.sum()
    return dict(n=len(t), net=t.net.sum(), dd=dd, rdd=t.net.sum() / abs(dd) if dd < 0 else np.inf,
                win=(t.net > 0).mean(), worst=t.net.min(), mpos=(m > 0).mean(),
                kept=t.total.sum() / t.short_prem.sum(), prem=t.short_prem.mean(),
                big=t[t.move.abs() >= 300].net.sum())


def configs():
    C = []
    add = lambda fam, label, **kw: C.append((fam, label, kw))
    # A. base: straddle multipliers x shift
    for kc, kp, sh in itertools.product((0.5, 0.6, 0.75, 0.9, 1.0, 1.25), (0.75, 0.9, 1.0, 1.25, 1.5), (0.0, 0.15)):
        add("A straddle multipliers", f"call {kc}× put {kp}× shift {sh}", kc=kc, kp=kp, shift=sh)
    # B. other units
    units = [("S/√n", dict(unit="S", p=0.5)), ("S/n", dict(unit="S", p=1.0)), ("realised 5d", dict(unit="R", N=5)),
             ("realised 10d", dict(unit="R", N=10)), ("realised 20d", dict(unit="R", N=20)),
             ("avg(S/√n, real10)", dict(unit="avg", N=10)), ("max(S/√n, real10)", dict(unit="max", N=10))]
    for (un, ukw), kc, kp, sh in itertools.product(units, (0.75, 1.0, 1.25, 1.5, 2.0, 2.5), (1.0, 1.25, 1.5, 2.0, 2.5, 3.0), (0.0, 0.15)):
        add("B " + un, f"{un}: call {kc}× put {kp}× shift {sh}", kc=kc, kp=kp, shift=sh, **ukw)
    # C. shift settings on base
    for c, n, cap in itertools.product((0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.4), (2, 3, 5, 10, 20), (None, 0.5, 1.0)):
        if c == 0.0 and (n != 5 or cap is not None):
            continue
        add("C trend shift", f"shift {c}×{n}d cap {cap}", kc=0.75, kp=1.0, shift=c, shift_n=n, shift_cap=cap)
    # D. floors (never closer than f x unit to spot)
    for f, (kc, kp), sh in itertools.product((0.0, 0.25, 0.5, 0.75), ((0.75, 1.0), (0.6, 1.0), (1.0, 1.0)), (0.15, 0.3)):
        add("D min-distance floor", f"floor {f}× · call {kc} put {kp} shift {sh}", kc=kc, kp=kp, shift=sh, floor=f)
    # E. premium relative to straddle
    for a, b in itertools.product((0.1, 0.15, 0.2, 0.25, 0.3, 0.4), (0.1, 0.15, 0.2, 0.25, 0.3, 0.4)):
        add("E premium = share of straddle", f"call prem {a}×S put prem {b}×S", mode="eq", eq=(a, b), shift=0.0)
    # F. fixed points
    for cd, pd_, sh in itertools.product((100, 150, 200, 250, 300, 400), (150, 200, 250, 300, 400, 500), (0.0, 0.15)):
        add("F fixed points", f"call +{cd} put −{pd_} shift {sh}", mode="fixed", fixed=(cd, pd_), shift=sh)
    # G. percent of spot
    for cp, pp, sh in itertools.product((0.005, 0.0075, 0.01, 0.0125), (0.0075, 0.01, 0.0125, 0.015, 0.0175), (0.0, 0.15)):
        add("G percent of spot", f"call +{cp*100:.2f}% put −{pp*100:.2f}% shift {sh}", mode="pct", pct=(cp, pp), shift=sh)
    # H. power scaling of distance with straddle size
    for g, (kc, kp) in itertools.product((0.5, 0.75, 1.0, 1.25, 1.5), ((0.75, 1.0), (1.0, 1.25))):
        add("H power scaling", f"distance ∝ S^{g} · call {kc} put {kp}", kc=kc, kp=kp, shift=0.15, gamma=g)
    # I. skip days with too little premium
    for mp_ in (0, 20, 30, 40, 50, 60):
        add("I minimum premium", f"skip if premium < {mp_}", kc=0.75, kp=1.0, shift=0.15, minprem=mp_)
    # J. separate Monday (1 day) / Friday (2 days) settings
    for d_, kc, kp, sh in itertools.product((1, 2), (0.5, 0.6, 0.75, 1.0, 1.25), (0.75, 1.0, 1.25, 1.5), (0.0, 0.15)):
        add(f"J only {d_}-day", f"{d_}-day only: call {kc} put {kp} shift {sh}", kc=kc, kp=kp, shift=sh, dtes=frozenset({d_}))
    return C


def main():
    os.makedirs(OUT, exist_ok=True)
    t0 = time.time()
    L = Lab(start="2020-11-15")
    C = configs()
    print(f"{len(C)} variants; loaded in {time.time()-t0:.0f}s", flush=True)
    rows = []
    for k, (fam, label, kw) in enumerate(C):
        t = L.run(fbuilder(**kw), WINDOWS["P1"][0])
        row = dict(id=k, family=fam, label=label)
        if len(t):
            t["net"] = t.total - CHARGE
            for w, (a, b) in WINDOWS.items():
                row.update({f"{w}_{kk}": v for kk, v in ev(t[(t.sell >= a) & (t.sell <= b)]).items()})
            y = t.groupby(t.sell.str[:4]).net.sum()
            row.update({f"y{yy}": y.get(str(yy), np.nan) for yy in range(2021, 2027)})
        rows.append(row)
        if k % 100 == 0:
            print(k, f"{time.time()-t0:.0f}s", flush=True)
    pd.DataFrame(rows).to_csv(os.path.join(OUT, "formula_grid.csv"), index=False, float_format="%.4f")
    print("done", f"{time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
