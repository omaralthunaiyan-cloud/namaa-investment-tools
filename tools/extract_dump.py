"""
Extract data/*.csv straight out of a PostgreSQL custom-format dump, without
needing a running database.

`pg_restore` before version 17 rejects this repo's dump outright:

    pg_restore: error: unsupported version (1.16) in file header

so this reads the archive directly with pgdumplib instead. Column order is
recovered from the CREATE TABLE statements the dump carries in its pre-data
section.

Usage:
    pip install pgdumplib pandas
    python tools/extract_dump.py path/to/Namaa_backup.dump
    python tools/extract_dump.py path/to/Namaa_backup.dump --all   # also historical_prices (9MB)
"""
import argparse
import csv
import os
import re

import pgdumplib

EXCLUDED_BY_DEFAULT = {"historical_prices"}


def get_columns(defn: str) -> list[str]:
    cols = []
    for line in defn.splitlines():
        line = line.strip()
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_]*)\s+", line)
        if m and not line.upper().startswith(("CREATE", "PRIMARY", "CONSTRAINT", ")")):
            cols.append(m.group(1))
    return cols


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("dump_path", help="Path to the .dump file (custom format)")
    ap.add_argument("--out", default="data", help="Output directory (default: data)")
    ap.add_argument("--all", action="store_true", help="Also extract historical_prices (9MB, not shipped by default)")
    args = ap.parse_args()

    dump = pgdumplib.load(args.dump_path)

    tables = {}
    for e in dump.entries:
        if e.desc == "TABLE" and e.namespace == "public":
            tables[e.tag] = get_columns(e.defn)

    os.makedirs(args.out, exist_ok=True)

    for e in dump.entries:
        if e.desc != "TABLE DATA" or e.namespace != "public":
            continue
        tag = e.tag
        if tag in EXCLUDED_BY_DEFAULT and not args.all:
            print(f"{tag}: skipped (pass --all to include; it's 9MB and nothing reads it at runtime)")
            continue
        cols = tables.get(tag)
        rows = list(dump.table_data("public", tag))
        out_path = os.path.join(args.out, f"{tag}.csv")
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(cols)
            w.writerows(rows)
        print(f"{tag}: {len(rows)} rows -> {out_path}")


if __name__ == "__main__":
    main()
