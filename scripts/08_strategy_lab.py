"""Strategy lab: many short-premium ideas on NSE end-of-day Nifty option prices.

Ground rules (as agreed): NSE closing price (or opening price for intraday ideas),
points per unit, no costs, only strikes that traded that day.

Each strategy is a function (lab, i) -> Position | None, where i indexes the
entry day. The engine prices the exit and returns one row per trade.
"""
import os, sys
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@dataclass
class Leg:
    expiry: str
    opt: str          # CE / PE
    strike: float
    sign: int         # -1 short, +1 long
    entry: float


@dataclass
class Position:
    legs: list
    exit: str = "next_close"   # next_close | same_close | expiry_close | hold
    stop: float = None         # stop multiple on short legs (checks highs after entry)
    note: str = ""
    max_days: int = None       # exit="hold": exit after this many trading days (or at expiry if sooner)
    take_profit: float = None  # exit at a close once this fraction of the net credit is captured
    close_stop: float = None   # exit at a close once cost-to-close >= this multiple of the net credit


class Lab:
    def __init__(self, start="2021-01-01", end=None):
        op = pd.read_csv(os.path.join(ROOT, "data", "nifty_options_all.csv.gz"))
        op = op[op.date >= start]
        if end:
            op = op[op.date <= end]
        ex = op[["date", "expiry"]].drop_duplicates()
        ex = ex[ex.expiry >= ex.date].sort_values(["date", "expiry"])
        ex["r"] = ex.groupby("date").cumcount()
        ex = ex[ex.r < 3]
        op = op.merge(ex[["date", "expiry"]], on=["date", "expiry"])
        self.days = sorted(op.date.unique())
        self.pos = {d: i for i, d in enumerate(self.days)}
        idx = pd.read_csv(os.path.join(ROOT, "data", "nifty_index.csv")).set_index("date")
        self.idx = idx
        self.spot = idx.close.to_dict()
        self.spot_open = idx.open.to_dict()
        self.allidx = list(idx.index)                 # for trailing realised moves
        self.exps = {d: sorted(g.expiry) for d, g in ex.groupby("date")}
        self.chain = {}
        cols = ["strike", "open", "high", "low", "close", "contracts", "oi"]
        for (d, e, o), g in op.groupby(["date", "expiry", "opt"], sort=False):
            g = g.sort_values("strike")
            self.chain[(d, e, o)] = {c: g[c].values.astype(float) for c in cols}

    # ---------- helpers
    def expiry(self, d, k=0, include_today=False):
        ex = [e for e in self.exps.get(d, []) if (e >= d if include_today else e > d)]
        return ex[k] if len(ex) > k else None

    def dte(self, d, e):
        n = sum(1 for x in self.days[self.pos[d] + 1:] if x <= e)
        last = self.days[-1]
        if e > last:  # expiry beyond the data: add weekdays after the last day (holidays unknown)
            n += int(np.busday_count(np.datetime64(last) + 1, np.datetime64(e) + 1))
        return n

    def q(self, d, e, o, k):
        c = self.chain.get((d, e, o))
        if c is None:
            return None
        i = np.searchsorted(c["strike"], k)
        if i < len(c["strike"]) and c["strike"][i] == k:
            return {f: c[f][i] for f in c}
        return None

    def traded(self, d, e, o, field="close", otm_of=None):
        c = self.chain.get((d, e, o))
        if c is None:
            return None
        ok = (c["contracts"] > 0) & (c[field] > 0)
        if otm_of is not None:
            ok &= (c["strike"] > otm_of) if o == "CE" else (c["strike"] < otm_of)
        return c, ok

    def by_price(self, d, e, o, target, field="close", otm_of=None, lo=None, hi=None):
        r = self.traded(d, e, o, field, otm_of)
        if r is None:
            return None
        c, ok = r
        if lo is not None:
            ok &= (c[field] >= lo) & (c[field] <= hi)
        if not ok.any():
            return None
        i = np.where(ok)[0]
        j = i[np.argmin(np.abs(c[field][i] - target))]
        return c["strike"][j], c[field][j]

    def by_strike(self, d, e, o, target_k, field="close"):
        """traded strike nearest target_k (OTM side preferred by rounding outward)."""
        r = self.traded(d, e, o, field)
        if r is None:
            return None
        c, ok = r
        if not ok.any():
            return None
        i = np.where(ok)[0]
        dist = np.abs(c["strike"][i] - target_k)
        j = i[np.argmin(dist + (1e-3 * (c["strike"][i] < target_k) if o == "CE" else 1e-3 * (c["strike"][i] > target_k)))]
        return c["strike"][j], c[field][j]

    def atm(self, d, e, field="close", spot=None):
        spot = spot if spot is not None else self.spot[d]
        ce, pe = self.chain.get((d, e, "CE")), self.chain.get((d, e, "PE"))
        if ce is None or pe is None:
            return None
        ks = sorted(set(ce["strike"][(ce["contracts"] > 0) & (ce[field] > 0)]) & set(pe["strike"][(pe["contracts"] > 0) & (pe[field] > 0)]))
        if not ks:
            return None
        k = min(ks, key=lambda x: abs(x - spot))
        return k, self.q(d, e, "CE", k)[field], self.q(d, e, "PE", k)[field]

    def realised(self, d, n=10):
        """mean |close-to-close move| over the n trading days up to and including d."""
        j = self.allidx.index(d)
        s = self.idx.close.iloc[max(0, j - n): j + 1]
        return s.diff().abs().mean()

    # ---------- engine
    def run(self, strat, start, end=None, name=None):
        rows = []
        for i, d in enumerate(self.days):
            if d < start or (end and d > end) or i >= len(self.days) - 1:
                continue
            p = strat(self, i)
            if p is None:
                continue
            r = self.price(i, p)
            if r is not None:
                rows.append(r)
        t = pd.DataFrame(rows)
        if name and len(t):
            t.insert(0, "strategy", name)
        return t

    def price(self, i, p):
        d = self.days[i]
        if p.exit == "same_close":
            path = [d]
        elif p.exit == "next_close":
            path = [self.days[i + 1]]
        elif p.exit == "hold":
            e = min(L.expiry for L in p.legs)
            path = [x for x in self.days[i + 1:] if x <= e][: p.max_days]
            if not path or (len(path) < p.max_days and path[-1] != e):
                return None
        else:  # expiry_close
            e = p.legs[0].expiry
            path = [x for x in self.days[i + 1:] if x <= e]
            if not path or path[-1] != e:
                return None
        if p.take_profit is not None or p.close_stop is not None:
            credit = sum(-L.sign * L.entry for L in p.legs)
            for j, day in enumerate(path):
                qs = [self.q(day, L.expiry, L.opt, L.strike) for L in p.legs]
                if any(qq is None for qq in qs):
                    return None
                cost = sum(-L.sign * qq["close"] for L, qq in zip(p.legs, qs))
                if (p.take_profit is not None and credit - cost >= p.take_profit * credit) or \
                   (p.close_stop is not None and cost >= p.close_stop * credit):
                    path = path[: j + 1]
                    break
        exits, stopped = {}, 0
        for day in path:
            for li, L in enumerate(p.legs):
                if li in exits:
                    continue
                qq = self.q(day, L.expiry, L.opt, L.strike)
                if qq is None:
                    return None
                if p.stop and L.sign < 0 and day != d and qq["contracts"] > 0 and qq["high"] >= p.stop * L.entry:
                    lvl = p.stop * L.entry
                    exits[li] = max(lvl, qq["open"]) if qq["open"] > 0 else lvl
                    stopped += 1
                elif day == path[-1]:
                    exits[li] = qq["close"]
        pnl = [L.sign * (exits[li] - L.entry) for li, L in enumerate(p.legs)]
        short_prem = sum(L.entry for L in p.legs if L.sign < 0)
        long_prem = sum(L.entry for L in p.legs if L.sign > 0)
        x = path[-1]
        return dict(sell=d, exit=x, expiry=p.legs[0].expiry, dte=self.dte(d, p.legs[0].expiry),
                    spot=self.spot[d], move=self.spot[x] - (self.spot[d] if p.exit != "same_close" else self.spot_open[d]),
                    short_prem=short_prem, long_prem=long_prem, total=sum(pnl), stopped=stopped,
                    legs="/".join(f"{'-' if L.sign < 0 else '+'}{int(L.strike)}{L.opt[0]}" for L in p.legs), note=p.note)


def stats(t, split="2026-04-01"):
    if t is None or len(t) == 0:
        return {}
    eq = t.total.cumsum()
    dd = (eq - eq.cummax()).min()
    m = t.groupby(t.sell.str[:7]).total.sum()
    return dict(trades=len(t), total=t.total.sum(), avg=t.total.mean(), win=(t.total > 0).mean(),
                worst=t.total.min(), max_dd=dd, ret_dd=t.total.sum() / abs(dd) if dd < 0 else np.inf,
                months_pos=f"{int((m > 0).sum())}/{len(m)}", h1=t[t.sell < split].total.sum(), h2=t[t.sell >= split].total.sum(),
                prem=t.short_prem.mean(), big=t[t.move.abs() >= 300].total.sum())
