"""Download Nifty 50 (^NSEI) and India VIX (^INDIAVIX) price history from Yahoo Finance.

Writes data/market/:
  nifty_1d.csv   daily OHLC since 2007
  vix_1d.csv     India VIX daily OHLC since 2008
  nifty_1h.csv   hourly bars, last ~2 years
  nifty_15m.csv  15-minute bars, last ~60 days
  nifty_5m.csv   5-minute bars, last ~60 days
  nifty_1m.csv   1-minute bars, last ~30 days (fetched in 7-day pieces)
Existing rows are kept, so re-running extends the history (Yahoo only serves a rolling window of
intraday data, so run this regularly if you want a longer minute-level archive).
"""
import json, os, sys, time, urllib.request, urllib.parse
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "market")
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"}


def fetch(symbol, interval, p1, p2):
    q = urllib.parse.urlencode({"period1": int(p1), "period2": int(p2), "interval": interval, "includePrePost": "false"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?{q}"
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40) as r:
                j = json.load(r)
            res = j["chart"]["result"]
            if not res:
                return pd.DataFrame()
            res = res[0]
            ts = res.get("timestamp") or []
            if not ts:
                return pd.DataFrame()
            qd = res["indicators"]["quote"][0]
            df = pd.DataFrame({"ts": pd.to_datetime(ts, unit="s", utc=True).tz_convert("Asia/Kolkata").tz_localize(None),
                               "open": qd["open"], "high": qd["high"], "low": qd["low"], "close": qd["close"], "volume": qd.get("volume")})
            return df.dropna(subset=["open", "high", "low", "close"])
        except Exception as e:
            err = e
            time.sleep(2 * (attempt + 1))
    print("  failed:", symbol, interval, err)
    return pd.DataFrame()


def merge_save(name, new):
    path = os.path.join(OUT, name)
    if os.path.exists(path):
        old = pd.read_csv(path, parse_dates=["ts"])
        new = pd.concat([old, new])
    new = new.drop_duplicates("ts", keep="last").sort_values("ts")
    new.to_csv(path, index=False, float_format="%.2f")
    return new


def main():
    os.makedirs(OUT, exist_ok=True)
    now = time.time()
    day = 86400
    d = fetch("^NSEI", "1d", 1190000000, now + day)
    d = merge_save("nifty_1d.csv", d); print("nifty 1d ", len(d), d.ts.min().date(), d.ts.max().date())
    v = fetch("^INDIAVIX", "1d", 1190000000, now + day)
    v = merge_save("vix_1d.csv", v); print("vix 1d   ", len(v), v.ts.min().date(), v.ts.max().date())
    h = fetch("^NSEI", "1h", now - 728 * day, now + day)
    h = merge_save("nifty_1h.csv", h); print("nifty 1h ", len(h), h.ts.min(), h.ts.max())
    for iv, name, back in (("15m", "nifty_15m.csv", 59), ("5m", "nifty_5m.csv", 59)):
        x = fetch("^NSEI", iv, now - back * day, now + day)
        x = merge_save(name, x); print(f"nifty {iv:3s} ", len(x), x.ts.min(), x.ts.max())
    frames = []
    for k in range(0, 5):  # 1-minute data: ~30 days available, 7 days per request
        a, b = now - (k + 1) * 7 * day, now - k * 7 * day + (day if k == 0 else 0)
        f = fetch("^NSEI", "1m", a, b)
        if len(f):
            frames.append(f)
    if frames:
        m = merge_save("nifty_1m.csv", pd.concat(frames)); print("nifty 1m  ", len(m), m.ts.min(), m.ts.max())


if __name__ == "__main__":
    main()
