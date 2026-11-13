"""Download NSE F&O bhavcopies (Nifty rows only) and daily Nifty 50 index OHLC.

Usage: python3 scripts/01_download.py [START YYYY-MM-DD] [END YYYY-MM-DD]
Writes:
  data/fo_daily/YYYYMMDD.csv.gz   Nifty options + futures rows, unified columns
  data/index_daily/YYYYMMDD.csv   Nifty 50 OHLC row for that day
Already-downloaded days are skipped, so re-running only fetches new days.
"""
import csv, gzip, io, os, sys, time, zipfile, datetime as dt
import urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FO_DIR = os.path.join(ROOT, "data", "fo_daily")
IDX_DIR = os.path.join(ROOT, "data", "index_daily")
HOSTS = ["https://archives.nseindia.com", "https://nsearchives.nseindia.com"]
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)", "Accept": "*/*"}
OUT_COLS = ["date", "instrument", "expiry", "strike", "opt", "open", "high", "low",
            "close", "settle", "contracts", "turnover_rs", "oi", "lot"]
MON = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def fetch(path):
    """Return bytes, or None if the file doesn't exist (holiday)."""
    not_found = 0
    for attempt in range(6):
        for host in HOSTS:
            try:
                req = urllib.request.Request(host + path, headers=UA)
                with urllib.request.urlopen(req, timeout=40) as r:
                    return r.read()
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    not_found += 1
            except Exception:
                pass
        if not_found >= 2 * len(HOSTS) - 1:  # consistently 404 -> holiday
            return None
        time.sleep(2 * (attempt + 1))
    return None


def old_rows(d, raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    text = z.read(z.namelist()[0]).decode("latin-1")
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        if r["SYMBOL"].strip() != "NIFTY" or r["INSTRUMENT"] not in ("OPTIDX", "FUTIDX"):
            continue
        exp = dt.datetime.strptime(r["EXPIRY_DT"].strip(), "%d-%b-%Y").date()
        opt = r["OPTION_TYP"].strip()
        out.append([d.isoformat(), r["INSTRUMENT"], exp.isoformat(), float(r["STRIKE_PR"]),
                    "" if opt == "XX" else opt, r["OPEN"], r["HIGH"], r["LOW"], r["CLOSE"],
                    r["SETTLE_PR"], r["CONTRACTS"], float(r["VAL_INLAKH"]) * 1e5,
                    r["OPEN_INT"], ""])
    return out


def new_rows(d, raw):
    z = zipfile.ZipFile(io.BytesIO(raw))
    text = z.read(z.namelist()[0]).decode("latin-1")
    out = []
    for r in csv.DictReader(io.StringIO(text)):
        if r["TckrSymb"].strip() != "NIFTY" or r["FinInstrmTp"] not in ("IDO", "IDF"):
            continue
        inst = "OPTIDX" if r["FinInstrmTp"] == "IDO" else "FUTIDX"
        out.append([d.isoformat(), inst, r["XpryDt"].strip(), float(r["StrkPric"] or 0),
                    r["OptnTp"].strip(), r["OpnPric"], r["HghPric"], r["LwPric"], r["ClsPric"],
                    r["SttlmPric"], r["TtlTradgVol"], r["TtlTrfVal"], r["OpnIntrst"],
                    r["NewBrdLotQty"]])
    return out


def new_path(d):
    return f"/content/fo/BhavCopy_NSE_FO_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"


def old_path(d):
    return f"/content/historical/DERIVATIVES/{d.year}/{MON[d.month-1]}/fo{d:%d}{MON[d.month-1]}{d.year}bhav.csv.zip"


def mkt_path(d):
    return f"/archives/fo/mkt/fo{d:%d%m%Y}.zip"


def mkt_rows(d, raw):
    """Market-activity report: fallback for days with no bhavcopy (e.g. 30 Mar 2021).
    No settlement price is published there, so close is used for settle."""
    z = zipfile.ZipFile(io.BytesIO(raw))
    out, seen = [], set()
    for name, is_opt in ((f"op{d:%d%m%Y}.csv", True), (f"fo{d:%d%m%Y}.csv", False)):
        if name not in z.namelist():
            continue
        text = z.read(name).decode("latin-1")
        for r in csv.DictReader(io.StringIO(text)):
            r = {k.strip().rstrip("*"): (v or "").strip() for k, v in r.items() if k}
            if r.get("SYMBOL") != "NIFTY" or r.get("INSTRUMENT") not in ("OPTIDX", "FUTIDX"):
                continue
            exp = dt.datetime.strptime(r["EXP_DATE"], "%d/%m/%Y").date().isoformat()
            strike = float(r.get("STR_PRICE") or 0)
            opt = r.get("OPT_TYPE", "")
            key = (r["INSTRUMENT"], exp, strike, opt)
            if key in seen:  # these files repeat rows
                continue
            seen.add(key)
            qty, cont = float(r["TRD_QTY"]), float(r["NO_OF_CONT"])
            c = float(r["CLOSE_PRICE"])
            lot = round(qty / cont) if cont else ""
            out.append([d.isoformat(), r["INSTRUMENT"], exp, strike, opt,
                        float(r["OPEN_PRICE"]), float(r["HI_PRICE"]), float(r["LO_PRICE"]), c, c,
                        int(cont), float(r.get("TRD_VAL") or 0) or qty * c,
                        int(float(r["OPEN_INT"])), lot])
    return out


def get_fo(d):
    dest = os.path.join(FO_DIR, f"{d:%Y%m%d}.csv.gz")
    if os.path.exists(dest):
        return "skip"
    order = [(new_path, new_rows), (old_path, old_rows)]
    if d < dt.date(2024, 7, 8):
        order.reverse()
    order.append((mkt_path, mkt_rows))
    for pathf, parser in order:
        raw = fetch(pathf(d))
        if raw:
            rows = parser(d, raw)
            if not rows:
                return "empty"
            tmp = dest + ".tmp"
            with gzip.open(tmp, "wt", newline="") as f:
                w = csv.writer(f)
                w.writerow(OUT_COLS)
                w.writerows(rows)
            os.replace(tmp, dest)
            return "ok"
    return "none"


def get_idx(d):
    dest = os.path.join(IDX_DIR, f"{d:%Y%m%d}.csv")
    if os.path.exists(dest):
        return "skip"
    raw = fetch(f"/content/indices/ind_close_all_{d:%d%m%Y}.csv")
    if not raw:
        return "none"
    for line in raw.decode("latin-1").splitlines():
        p = line.split(",")
        if p[0].strip().lower() == "nifty 50":
            with open(dest, "w") as f:
                f.write(f"{d.isoformat()},{p[2]},{p[3]},{p[4]},{p[5]}\n")
            return "ok"
    return "none"


def main():
    start = dt.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else dt.date(2020, 1, 1)
    end = dt.date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else dt.date.today()
    os.makedirs(FO_DIR, exist_ok=True)
    os.makedirs(IDX_DIR, exist_ok=True)
    days = [start + dt.timedelta(i) for i in range((end - start).days + 1)]
    days = [d for d in days if d.weekday() < 5]
    fo_days = [d for d in days if d >= dt.date(2021, 1, 1)]
    with ThreadPoolExecutor(8) as ex:
        res_i = list(ex.map(get_idx, days))
        print("index:", {k: res_i.count(k) for k in set(res_i)}, flush=True)
        res_f = list(ex.map(get_fo, fo_days))
        print("fo:", {k: res_f.count(k) for k in set(res_f)}, flush=True)
    # Days with index data but no F&O file are worth flagging
    idx_ok = {d for d, r in zip(days, res_i) if r in ("ok", "skip")}
    fo_ok = {d for d, r in zip(fo_days, res_f) if r in ("ok", "skip")}
    missing = sorted(d for d in idx_ok if d >= dt.date(2021, 1, 1) and d not in fo_ok)
    print("trading days missing F&O:", [d.isoformat() for d in missing])


if __name__ == "__main__":
    main()
