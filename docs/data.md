# Data

Everything traces to `Namaa_backup.dump`, a PostgreSQL 17 custom-format dump taken on 24 November 2025. The CSVs in `data/` (except `historical_prices`, see below) are the real export from that dump, committed in this repo — not samples.

## Getting at it

`pg_restore` before version 17 rejects the file outright:

```
pg_restore: error: unsupported version (1.16) in file header
```

Rather than requiring a PostgreSQL 17 install, `tools/extract_dump.py` reads the archive directly:

```bash
pip install pgdumplib pandas
python tools/extract_dump.py path/to/Namaa_backup.dump
```

No server, no `createdb`, no restore. Column order is recovered from the `CREATE TABLE` statements the dump carries in its pre-data section.

## Tables

| Table | Rows | Shipped in `data/` | Notes |
|---|---:|---|---|
| `companies` | 270 | yes | symbol, name, sector |
| `dividend_ttm` | 128 | yes | trailing dividend per share |
| `dividends` | 1,258 | yes | individual distributions, 2020–2026 |
| `indices` | 983 | yes | raw fundamentals as filed |
| `indices_cleaned` | 2,706 | yes | same, gap-filled to a full 2014–2024 grid |
| `indices_features` | 983 | yes | `indices` plus `earnings_yield` |
| `yearly_prices_final` | 2,528 | yes | average close price per company-year |
| `prices_coverage` | 264 | yes | which date range each symbol has prices for |
| `historical_prices` | 272,235 | no | daily closes; 9 MB, nothing at runtime reads more than the latest one per symbol |

Recover the excluded table with `--all`, then derive `data/last_close.csv` (264 rows — one close per symbol) with `python tools/compute_last_close.py`. That small derived file, not the full 272,235-row table, is what `tools/build_payload.py` and the repo actually ship.

## The join the model trains on

The dump defines a few views the original scripts query against a live database; this repo doesn't run PostgreSQL, so the one view that matters — `v_model_base` — is reconstructed in pandas instead, inside `tools/train_model.py`:

- Symbols are normalised by stripping a `.SR` suffix where present (`base_symbol()` in each tool script), applied on load everywhere.
- `v_model_base` = `indices_cleaned` **inner-joined** to `yearly_prices_final` on symbol and year. Reconstructing it this way gives 1,903 rows across 185 companies — the inner join is why 270 companies become 185 for the growth model specifically (every other tool still sees all 270).

## Quirks

**Symbols appear in two forms.** Some feeds write `1010`, others `1010.SR`. Normalised on load.

**One sector has a stray leading space.** The database's `sector` column has both `"Insurance"` and `" Insurance"` — same sector, two distinct strings, one company (symbol 8110, Saudi Indian Company for Cooperative Insurance). Trimmed on load.

**Sector names are abbreviated in the database.** `Commercial & Professional Svc`, `Health Care Equipment & Svc`, `Real Estate Mgmt & Dev't` — a UI that shows a different, longer label for these while filtering against the stored abbreviation will silently return nothing. This build's sector picker is generated straight from the stored values, so there's no separate mapping to keep in sync.

**Eleven companies have a blank sector in the loose `Companies.csv`** that shipped alongside the original scripts. The database has them filled in. Building from the database (as this repo does) picks up all eleven.

**Two extra sectors beyond the original 22.** `Closed-End Fund` (four traded funds) and `Unknown` (two sukuk ETFs). `Unknown` is excluded from the sector picker; `Closed-End Fund` is included, giving 23 sectors on the picker.

**`indices_cleaned` is mostly repetition.** It was gap-filled to a complete 2014–2024 grid per company, so 1,752 of its 2,706 rows repeat the previous year verbatim. `tools/build_payload.py` run-length encodes this: a bare year in `web/data.js` means "same indicator values as the entry before it."

**`dividend_ttm` for some symbols carries float drift from upstream** (e.g. a value like `0.3399999999999999` rather than `0.34`). Preserved as-is rather than silently rounded at the data layer; the UI rounds for display.

## Precision in the browser payload

`tools/build_payload.py` stores capital, total liabilities and net income in millions with three decimals — a rounding error well below the precision of the filings themselves, against values in the billions. Ratio fields (ROE, ROA, P/E, EPS, BVPS, D/E) keep four or five decimals. The UI rounds to two decimals for display either way.
