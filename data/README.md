# data

CSV export of the PostgreSQL database in `Namaa_backup.dump` — the real export, committed here, not samples. `historical_prices` (272,235 rows, 9 MB) is the one table excluded by default; see [`../docs/data.md`](../docs/data.md).

Regenerate with:

    python tools/extract_dump.py path/to/Namaa_backup.dump

Three files here are not raw exports:

| File | Contents |
|---|---|
| `last_close.csv` | one row per symbol, its most recent close price — derived from `historical_prices` by `tools/compute_last_close.py` (needs `--all` on the extract step first) |
| `predicted_prices_rf.csv` | Random Forest projections for 2025-2027, written by `tools/train_model.py` |
| `last_actual_prices.csv` | each company's most recent realised annual average price, also written by `tools/train_model.py` |

See `../docs/data.md` for table-level notes and known quirks.
