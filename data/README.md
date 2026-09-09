# data

CSV export of the PostgreSQL database in `Namaa_backup.dump`.

Regenerate with:

    python tools/extract_dump.py path/to/Namaa_backup.dump

Two files are not exports — they are model output, rewritten by
`python -m engine.cli train`:

| File | Contents |
|---|---|
| `predicted_prices_rf.csv` | Random Forest projections for 2025-2027, 555 rows |
| `last_actual_prices.csv` | each company's most recent realised annual average price |

See `../docs/data.md` for table-level notes and known quirks.
