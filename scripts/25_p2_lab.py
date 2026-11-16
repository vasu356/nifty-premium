"""P2 (Tuesday-expiry era, Sep 2025 ->) deep study of alternative ways to capture premium decay.

Every trade: sell at the close of the entry day, nearest expiry. Exit either at the next trading day's close ("next") or
held to expiry ("expiry", settled at intrinsic value from the Nifty close on expiry day), optionally with a daily
close-based stop. Charges: 1 point per leg per lot (Rs 65 at 65 units) — the agreed Rs 130 per 2-leg trade.
Selection uses H1 = Sep 2025..Feb 2026, confirmation H2 = Mar 2026..now; P1 (2021..Aug 2025) only as a sanity check.
"""
import os, sys, importlib, itertools
import numpy as np, pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
labm = importlib.import_module("08_strategy_lab")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "results", "manual")
L = labm.Lab(start="2020-11-15")
SPOT = L.spot
H1_END, P2_START = "2026-02-28", "2025-09-01"


def ref(d, n=5):
    j = L.allidx.index(d)
    return L.idx.close.iloc[j - n]


INTRINSIC = True


def leg_value(x, e, o, k):
    """value of option (e,o,k) at the close of day x; intrinsic on expiry day (if INTRINSIC)."""
    if x == e and INTRINSIC:
        s = SPOT[x]
        return max(0.0, s - k) if o == "CE" else max(0.0, k - s)
    q = L.q(x, e, o, k)
    return None if q is None else q["close"]


def pick(d, e, o, spec, S, centre):
    sp = SPOT[d]
    sel = spec.get("sel", "S")
    if sel == "S":
        m = spec["kc"] if o == "CE" else spec["kp"]
        tgt = centre + m * S if o == "CE" else centre - m * S
        if m > 0:                       # never let the trend shift push a short leg in the money
            tgt = max(tgt, sp) if o == "CE" else min(tgt, sp)
        return L.by_strike(d, e, o, tgt)
    if sel == "prem":
        return L.by_price(d, e, o, spec["X"], otm_of=sp)
    if sel == "frac":
        f = spec["fc"] if o == "CE" else spec["fp"]
        return L.by_price(d, e, o, f * S, otm_of=sp)
    if sel == "pct":
        m = spec["pc"] if o == "CE" else spec["pp"]
        return L.by_strike(d, e, o, centre * (1 + m / 100) if o == "CE" else centre * (1 - m / 100))
    raise ValueError(sel)


def trade(i, spec):
    d = L.days[i]
    e = L.expiry(d, k=spec.get("ek", 0))
    if e is None or e > L.days[-1]:
        return None
    n = L.dte(d, e)
    if n not in spec["dtes"]:
        return None
    at = L.atm(d, e)
    if at is None:
        return None
    S = at[1] + at[2]
    sp = SPOT[d]
    centre = sp + spec.get("sh", 0.0) * (sp - ref(d))
    legs = []          # (opt, strike, qty(+short), entry)
    sides = spec.get("sides", ("CE", "PE"))
    for o in sides:
        r = pick(d, e, o, spec, S, centre)
        if r is None:
            return None
        legs.append([o, r[0], spec.get("q" + o, 1.0), r[1]])
    w = spec.get("wing")
    if w:
        for o, k, qq, _ in list(legs):
            kk = k + w * S if o == "CE" else k - w * S
            r = L.by_strike(d, e, o, kk)
            if r is None or r[0] == k:
                return None
            legs.append([o, r[0], -qq, r[1]])
    credit = sum(q * px for _, _, q, px in legs)
    path = [L.days[i + 1]] if spec["exit"] == "next" else [x for x in L.days[i + 1:] if x <= e]
    if not path or (spec["exit"] == "expiry" and path[-1] != e):
        return None
    stop = spec.get("stop")
    exit_day, cost = None, None
    for x in path:
        vals = [leg_value(x, e, o, k) for o, k, _, _ in legs]
        if any(v is None for v in vals):
            return None
        c = sum(q * v for (o, k, q, _), v in zip(legs, vals))
        if stop and x != path[-1] and c >= stop * credit:
            exit_day, cost = x, c
            break
        exit_day, cost = x, c
    charges = sum(abs(q) for _, _, q, _ in legs) * 1.0
    return dict(sell=d, exit=exit_day, expiry=e, dte=n, spot=sp, S=S, credit=credit, pnl=credit - cost, net=credit - cost - charges,
                legs="/".join(f"{'-' if q > 0 else '+'}{abs(q):g}x{int(k)}{o[0]}" for o, k, q, _ in legs),
                move=SPOT[exit_day] - sp)


def run(spec, start=P2_START, end=None):
    rows = []
    for i, d in enumerate(L.days[:-1]):
        if d < start or (end and d > end):
            continue
        r = trade(i, spec)
        if r:
            rows.append(r)
    return pd.DataFrame(rows)


def summ(t, name=""):
    if t is None or len(t) == 0:
        return dict(name=name, n=0)
    t = t.sort_values("sell")
    eq = t.net.cumsum()
    m = t.groupby(t.sell.str[:7]).net.sum()
    h1, h2 = t[t.sell <= H1_END], t[t.sell > H1_END]
    worst = t.net.nsmallest(3)
    return dict(name=name, n=len(t), credit=t.credit.mean(), net=t.net.sum(), avg=t.net.mean(), med=t.net.median(),
                win=(t.net > 0).mean() * 100, worst=t.net.min(), ex_w1=t.net.sum() - worst.iloc[:1].sum(), ex_w3=t.net.sum() - worst.sum(),
                dd=(eq - eq.cummax()).min(), kept=t.pnl.sum() / t.credit.sum() * 100, m_pos=f"{(m > 0).sum()}/{len(m)}",
                H1=h1.net.sum(), H2=h2.net.sum(), H1_ex=h1.net.sum() - h1.net.nsmallest(1).sum(), H2_ex=h2.net.sum() - h2.net.nsmallest(1).sum())
