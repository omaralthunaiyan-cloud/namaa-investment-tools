"""
Derive data/last_close.csv (one row per symbol: its most recent close price)
from historical_prices, which is NOT shipped in data/ by default (9MB, and
nothing else at runtime reads it - see tools/extract_dump.py).

Only the dividend recommender needs a last close price (to turn trailing
dividend into a yield), so this reduces 272,235 daily rows to ~264.

Usage:
    python tools/extract_dump.py path/to/Namaa_backup.dump --all   # writes data/historical_prices.csv
    python tools/compute_last_close.py
"""
import csv
import re

DATA = "data"


def base_symbol(s):
    return re.sub(r"\.SR$", "", str(s))


def main():
    last_close, last_date = {}, {}
    with open(f"{DATA}/historical_prices.csv", encoding="utf-8") as f:
        header = f.readline().strip().split(",")
        si, di, ci = header.index("symbol"), header.index("date"), header.index("close_price")
        for line in f:
            parts = line.rstrip("\n").split(",")
            if len(parts) < 3:
                continue
            sym, date, close = base_symbol(parts[si]), parts[di], parts[ci]
            if not date or not close:
                continue
            if sym not in last_date or date > last_date[sym]:
                last_date[sym] = date
                try:
                    last_close[sym] = float(close)
                except ValueError:
                    pass

    with open(f"{DATA}/last_close.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["symbol", "last_close"])
        for sym in sorted(last_close):
            w.writerow([sym, round(last_close[sym], 2)])

    print(f"[INFO] wrote {DATA}/last_close.csv for {len(last_close)} symbols")


if __name__ == "__main__":
    main()
