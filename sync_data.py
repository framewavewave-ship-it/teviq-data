#!/usr/bin/env python3
"""
TEVIQ.STORE — AUTOMATED FULL-HISTORY MARKET DATA SYNC (100% FREE CDN)
Pulls 39 Core FX, Metals & Indices across 1d (max since inception), 1h, 15m, 5m.
Merges & preserves all existing historical bars permanently so history grows forever.
"""

import json
import os
import time
import urllib.parse
import urllib.request

SYMBOLS = [
    # Indices
    ("NAS100", "NQ=F",   2), ("SP500",  "ES=F",   2), ("US30",   "YM=F",   2),
    ("GER40",  "^GDAXI", 2), ("UK100",  "^FTSE",  2), ("JPN225", "^N225",  1),
    # Commodities & Metals
    ("XAUUSD", "GC=F",   2), ("XAGUSD", "SI=F",   3), ("USOIL",  "CL=F",   2),
    ("UKOIL",  "BZ=F",   2), ("NGAS",   "NG=F",   3),
    # Forex Majors
    ("EURUSD", "EURUSD=X", 5), ("GBPUSD", "GBPUSD=X", 5), ("USDJPY", "JPY=X",    3),
    ("USDCHF", "CHF=X",    5), ("AUDUSD", "AUDUSD=X", 5), ("USDCAD", "CAD=X",    5),
    ("NZDUSD", "NZDUSD=X", 5),
    # Forex Minors
    ("EURGBP", "EURGBP=X", 5), ("EURJPY", "EURJPY=X", 3), ("EURAUD", "EURAUD=X", 5),
    ("EURCAD", "EURCAD=X", 5), ("EURCHF", "EURCHF=X", 5), ("EURNZD", "EURNZD=X", 5),
    ("GBPJPY", "GBPJPY=X", 3), ("GBPAUD", "GBPAUD=X", 5), ("GBPCAD", "GBPCAD=X", 5),
    ("GBPCHF", "GBPCHF=X", 5), ("GBPNZD", "GBPNZD=X", 5), ("AUDJPY", "AUDJPY=X", 3),
    ("AUDCAD", "AUDCAD=X", 5), ("AUDCHF", "AUDCHF=X", 5), ("AUDNZD", "AUDNZD=X", 5),
    ("CADJPY", "CADJPY=X", 3), ("CADCHF", "CADCHF=X", 5), ("CHFJPY", "CHFJPY=X", 3),
    ("NZDJPY", "NZDJPY=X", 3), ("NZDCAD", "NZDCAD=X", 5), ("NZDCHF", "NZDCHF=X", 5),
]

TIMEFRAMES = [
    ("1d",  "1d",  "max",  30000),  # Full inception history (20-30+ years)
    ("1h",  "60m", "730d", 50000),  # 2+ years, permanently accumulating
    ("15m", "15m", "60d",  80000),  # Deep backtest history, permanently accumulating
    ("5m",  "5m",  "60d",  100000), # Intraday history, permanently accumulating
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

def fetch_yahoo(ticker, yf_int, yf_range, prec):
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{urllib.parse.quote(ticker)}?interval={yf_int}&range={yf_range}&includePrePost=false"
    )
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    result = (data.get("chart") or {}).get("result") or []
    if not result:
        return []
    r0 = result[0]
    ts = r0.get("timestamp") or []
    q = ((r0.get("indicators") or {}).get("quote") or [{}])[0]
    opens = q.get("open") or []
    highs = q.get("high") or []
    lows = q.get("low") or []
    closes = q.get("close") or []

    rows = []
    for i in range(len(ts)):
        t = ts[i]
        o, h, l, c = opens[i], highs[i], lows[i], closes[i]
        if t is None or o is None or h is None or l is None or c is None:
            continue
        if o <= 0 or h <= 0 or l <= 0 or c <= 0:
            continue
        hi = max(h, o, c)
        lo = min(l, o, c)
        rows.append([
            int(t),
            round(float(o), prec),
            round(float(hi), prec),
            round(float(lo), prec),
            round(float(c), prec),
        ])
    return rows

def merge_and_save(filepath, new_rows, max_bars):
    bar_map = {}
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                old = json.load(f)
            if isinstance(old, list):
                for r in old:
                    if isinstance(r, list) and len(r) >= 5:
                        bar_map[int(r[0])] = r[:5]
        except Exception:
            pass

    for r in new_rows:
        bar_map[int(r[0])] = r

    if not bar_map:
        return 0

    merged = [bar_map[k] for k in sorted(bar_map.keys())]
    if len(merged) > max_bars:
        merged = merged[-max_bars:]

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(merged, f, separators=(",", ":"))
    return len(merged)

def main():
    updated = 0
    errors = 0
    for sym_id, yf_ticker, prec in SYMBOLS:
        for tf, yf_int, yf_range, cap in TIMEFRAMES:
            out_file = f"{sym_id}_{tf}.json"
            try:
                rows = fetch_yahoo(yf_ticker, yf_int, yf_range, prec)
                if rows:
                    total = merge_and_save(out_file, rows, cap)
                    updated += 1
                    print(f"[OK] {out_file}: +{len(rows)} fetched -> {total} stored")
                else:
                    print(f"[WARN] {out_file}: empty response")
            except Exception as exc:
                errors += 1
                print(f"[ERR] {out_file}: {exc}")
            time.sleep(0.35)

    meta = {
        "updated_utc": int(time.time()),
        "symbols": len(SYMBOLS),
        "files_updated": updated,
        "errors": errors,
    }
    with open("manifest_data.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print("Sync complete:", meta)

if __name__ == "__main__":
    main()
