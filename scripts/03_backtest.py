"""Backtest engine for short Nifty option strategies (premium decay).

All P&L is in Nifty points per unit (1 point = Rs 1 per unit; multiply by lot size
for Rs per lot). Entries and exits use bhavcopy closing prices; options held to
expiry settle at intrinsic value against the Nifty 50 close on expiry day.
"""
import os
from dataclasses import dataclass, field
from typing import Optional
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(ROOT, "data")


# ---------------------------------------------------------------- data
class Market:
    def __init__(self):
        op = pd.read_csv(os.path.join(D, "nifty_options_all.csv.gz"),
                         usecols=["date", "expiry", "strike", "opt", "open", "high", "close", "contracts"],
                         parse_dates=["date", "expiry"])
        # keep only the 3 nearest expiries (>= date) per day; strategies never go further
        exps = op[["date", "expiry"]].drop_duplicates()
        exps = exps[exps.expiry >= exps.date].sort_values(["date", "expiry"])
        exps["rank"] = exps.groupby("date").cumcount()
        exps = exps[exps["rank"] < 3]
        op = op.merge(exps[["date", "expiry"]], on=["date", "expiry"])
        self.tdays = np.array(sorted(op.date.unique()), dtype="datetime64[ns]")
        self.tpos = {pd.Timestamp(d): i for i, d in enumerate(self.tdays)}
        idx = pd.read_csv(os.path.join(D, "nifty_index.csv"), parse_dates=["date"]).set_index("date")
        self.spot = idx.close
        self.spot_open = idx.open
        self.lot = pd.read_csv(os.path.join(D, "lot_sizes.csv"), parse_dates=["date"]).set_index("date").lot
        # chain[(date, expiry, opt)] = (strikes, open, high, close, contracts) sorted by strike
        self.chain = {}
        for (d, e, o), g in op.groupby(["date", "expiry", "opt"], sort=False):
            g = g.sort_values("strike")
            self.chain[(d, e, o)] = (g.strike.values, g.open.values, g.high.values,
                                     g.close.values, g.contracts.values)
        self.expiries = {d: sorted(g.expiry) for d, g in exps.groupby("date")}
        self.last_day = pd.Timestamp(self.tdays[-1])

    def next_expiry(self, d):
        for e in self.expiries.get(d, []):
            if e > d:
                return e
        return None

    def dte(self, d, e):
        """Trading days from d to expiry e (1 = expiry is the next trading day)."""
        return int(np.searchsorted(self.tdays, np.datetime64(e)) - self.tpos[d])

    def quote(self, d, e, o, k):
        c = self.chain.get((d, e, o))
        if c is None:
            return None
        i = np.searchsorted(c[0], k)
        if i < len(c[0]) and c[0][i] == k:
            return {"open": c[1][i], "high": c[2][i], "close": c[3][i], "contracts": c[4][i]}
        return None

    def intrinsic(self, e, o, k):
        s = self.spot.get(e)
        if s is None or np.isnan(s):
            return None
        return max(0.0, s - k) if o == "CE" else max(0.0, k - s)


# ---------------------------------------------------------------- costs
@dataclass
class Costs:
    slip: float = 0.5          # points per side per leg
    brokerage: float = 20.0    # Rs per executed order
    on: bool = True

    def leg(self, d, lot, entry_px, exit_px, settled, is_short=True):
        """Costs in points/unit for one leg round trip.
        Short leg: sell at entry, buy back at exit (or expire/settle: no closing order).
        Long leg:  buy at entry, sell at exit (or settle: STT 0.125% on ITM exercise value)."""
        if not self.on:
            return 0.0
        new_regime = d >= pd.Timestamp("2024-10-01")
        stt_rate = 0.001 if new_regime else 0.000625
        txn_rate = 0.0003503 if new_regime else 0.0005
        sell_px, buy_px = (entry_px, exit_px) if is_short else (exit_px, entry_px)
        sell_traded = not (settled and not is_short)   # long leg settled -> no sell order
        buy_traded = not (settled and is_short)        # short leg settled -> no buy order
        orders = int(sell_traded) + int(buy_traded)
        turnover = sell_px * sell_traded + buy_px * buy_traded
        brok = self.brokerage * orders / lot
        txn = txn_rate * turnover
        sebi = 1e-6 * turnover
        gst = 0.18 * (brok + txn + sebi)
        stt = stt_rate * sell_px * sell_traded
        if settled and not is_short and exit_px > 0:
            stt += 0.00125 * exit_px
        stamp = 0.00003 * buy_px * buy_traded
        slip = self.slip * orders
        return brok + txn + sebi + gst + stt + stamp + slip


# ---------------------------------------------------------------- strategy
@dataclass
class Strategy:
    sid: str
    name: str
    group: str
    select: str = "premium"          # premium | distance | atm
    target: float = 30.0             # premium target (select=premium)
    band: float = 5.0                # +/- band around target
    distance: float = 0.0            # OTM points (select=distance)
    legs: tuple = ("CE", "PE")
    dte: Optional[set] = None        # allowed trading-days-to-expiry at entry; None = all
    hold: str = "overnight"          # overnight | expiry
    entry_dte_exact: Optional[int] = None
    wing: Optional[float] = None     # buy protective wing at this premium (iron condor)
    stop: Optional[float] = None     # stop at this multiple of entry premium (per leg)
    exact_stop_fill: bool = False    # True = fill exactly at stop even on gaps (unrealistic)
    skip_after_move: Optional[float] = None  # skip entry if today's |move| exceeds this
    description: str = ""
    user: bool = False


def pick_premium(c, target, band, side, spot):
    strikes, _, _, close, contracts = c
    ok = (contracts > 0) & (close >= target - band) & (close <= target + band)
    # OTM only
    ok &= (strikes > spot) if side == "CE" else (strikes < spot)
    if not ok.any():
        return None
    i = np.where(ok)[0]
    dist = np.abs(close[i] - target)
    best = i[dist == dist.min()]
    # tie: prefer further OTM
    j = best[-1] if side == "CE" else best[0]
    return strikes[j], close[j]


def pick_strike(c, k):
    strikes, _, _, close, contracts = c
    i = np.searchsorted(strikes, k)
    if i < len(strikes) and strikes[i] == k and contracts[i] > 0:
        return strikes[i], close[i]
    return None


def pick_wing(c, side, short_k, target):
    strikes, _, _, close, contracts = c
    ok = (contracts > 0) & ((strikes > short_k) if side == "CE" else (strikes < short_k)) & (close > 0)
    if not ok.any():
        return None
    i = np.where(ok)[0]
    j = i[np.argmin(np.abs(close[i] - target))]
    return strikes[j], close[j]


def run(m: Market, s: Strategy, costs: Costs = None):
    costs = costs or Costs()
    trades = []
    tdays = [pd.Timestamp(x) for x in m.tdays]
    i = 0
    while i < len(tdays) - 1:
        d = tdays[i]
        e = m.next_expiry(d)
        if e is None or e > m.last_day:
            i += 1
            continue
        n = m.dte(d, e)
        if s.dte is not None and n not in s.dte:
            i += 1
            continue
        spot = m.spot.get(d)
        if spot is None or np.isnan(spot):
            i += 1
            continue
        if s.skip_after_move is not None and i > 0:
            prev = m.spot.get(tdays[i - 1])
            if prev is not None and abs(spot - prev) > s.skip_after_move:
                i += 1
                continue
        exit_day = tdays[i + 1] if s.hold == "overnight" else e
        lot = int(m.lot.get(d, 75))
        legs = []
        ok = True
        for side in s.legs:
            c = m.chain.get((d, e, side))
            if c is None:
                ok = False
                break
            if s.select == "premium":
                p = pick_premium(c, s.target, s.band, side, spot)
            elif s.select == "atm":
                p = pick_strike(c, round(spot / 50) * 50)
            else:
                k = (np.ceil((spot + s.distance) / 50) * 50) if side == "CE" else (np.floor((spot - s.distance) / 50) * 50)
                p = pick_strike(c, k)
            if p is None:
                ok = False
                break
            legs.append((side, p[0], p[1], -1))
            if s.wing is not None:
                w = pick_wing(c, side, p[0], s.wing)
                if w is None:
                    ok = False
                    break
                legs.append((side, w[0], w[1], +1))
        if not ok or not legs:
            i += 1
            continue

        # walk forward day by day to the exit day, checking stops
        j = i + 1
        exits = {}
        stopped = set()
        while True:
            day = tdays[j]
            for li, (side, k, px, sign) in enumerate(legs):
                if li in exits:
                    continue
                if sign < 0 and s.stop is not None:
                    q = m.quote(day, e, side, k)
                    lvl = s.stop * px
                    if q is not None and q["high"] >= lvl:
                        fill = lvl if s.exact_stop_fill else max(lvl, q["open"])
                        exits[li] = (fill, False, day)
                        stopped.add(li)
                        continue
                if day == exit_day:
                    if day == e:
                        v = m.intrinsic(e, side, k)
                        exits[li] = (v, True, day)
                    else:
                        q = m.quote(day, e, side, k)
                        exits[li] = (None if q is None else q["close"], False, day)
            if day >= exit_day or len(exits) == len(legs):
                break
            j += 1
        if len(exits) < len(legs) or any(v[0] is None for v in exits.values()):
            i += 1
            continue
        # if a short leg is stopped, close its wing at the same time
        for li in list(stopped):
            side, k, px, sign = legs[li]
            for lj, (s2, k2, p2, sg2) in enumerate(legs):
                if sg2 > 0 and s2 == side and lj not in stopped:
                    q = m.quote(exits[li][2], e, s2, k2)
                    if q is not None:
                        exits[lj] = (q["close"], False, exits[li][2])
        gross = 0.0
        cost = 0.0
        for li, (side, k, px, sign) in enumerate(legs):
            xp, settled, _ = exits[li]
            gross += (px - xp) if sign < 0 else (xp - px)
            cost += costs.leg(d, lot, px, xp, settled, is_short=sign < 0)
        x_day = max(v[2] for v in exits.values())
        nxt = tdays[i + 1]
        trades.append({
            "date": d, "exit": x_day, "expiry": e, "dte": n, "lot": lot,
            "spot": spot, "move": m.spot.get(nxt, np.nan) - spot,
            "premium": sum(px for (_, _, px, sg) in legs if sg < 0),
            "strikes": "/".join(f"{int(k)}{side[0]}{'+' if sg > 0 else ''}" for side, k, _, sg in legs),
            "gross": gross, "cost": cost, "net": gross - cost, "stopped": len(stopped),
        })
        # overnight trades can be entered every day; hold-to-expiry moves past the expiry
        i = (m.tpos[x_day] if s.hold == "expiry" else i + 1)
    return pd.DataFrame(trades)


def summarize(s: Strategy, t: pd.DataFrame, ref_lot=65):
    if t.empty:
        return {"sid": s.sid, "name": s.name, "group": s.group, "trades": 0}
    eq = t.net.cumsum()
    dd = (eq - eq.cummax()).min()
    yr = t.groupby(t.date.dt.year).net.sum()
    daily = t.groupby("date").net.sum()
    return {
        "sid": s.sid, "name": s.name, "group": s.group, "user": s.user,
        "description": s.description, "trades": len(t),
        "gross": t.gross.sum(), "costs": t.cost.sum(), "net": t.net.sum(),
        "net_rs_per_lot": t.net.sum() * ref_lot,
        "avg_net": t.net.mean(), "avg_premium": t.premium.mean(),
        "win_rate": (t.net > 0).mean(), "max_dd": dd, "worst": t.net.min(), "best": t.net.max(),
        "sharpe": daily.mean() / daily.std() * np.sqrt(252) if daily.std() > 0 else np.nan,
        "years_pos": int((yr > 0).sum()), "years": int(len(yr)),
        **{f"y{y}": v for y, v in yr.items()},
    }
