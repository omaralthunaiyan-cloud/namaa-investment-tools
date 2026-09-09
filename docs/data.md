# Data

Everything traces to `Namaa_backup.dump`, a PostgreSQL 17 custom-format dump taken on 24 November 2025.

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
| `historical_prices` | 272,235 | no | daily closes; 9 MB, nothing reads it at runtime |

Recover the excluded table with `--all`.

## Views rebuilt in Python

The dump defines three views the original scripts query. `engine/data.py` reconstructs the one that matters:

- `indices_cleaned_base` — strips the `.SR` suffix from symbols. Handled by `data.base_symbol()`, applied on load to every table, so nothing downstream has to think about it.
- `v_model_base` — `indices_cleaned_base` inner-joined to `yearly_prices_final` on symbol and year. This is `data.model_base()`: 1,903 rows, 185 companies. The inner join is why 270 companies become 185.
- `v_indices_features_norm` — same suffix stripping over `indices_features`. Not used; `indices_features` only adds `earnings_yield`, which the Random Forest does not take.

## Quirks

**Symbols appear in two forms.** Some feeds write `1010`, others `1010.SR`. Normalised on load.

**Sector spellings differ between the CSVs and the UI.** The database stores abbreviated forms:

| Stored | Written out |
|---|---|
| `Commercial & Professional Svc` | Commercial & Professional Services |
| `Health Care Equipment & Svc` | Health Care Equipment & Services |
| `Real Estate Mgmt & Dev't` | Real Estate Management & Development |

The web prototype offered the long forms as filter options while filtering against the short ones, so those three sectors returned nothing. `SECTOR_TO_DATA` in the browser build maps them.

**Eleven companies have a blank sector in the loose `Companies.csv`.** The database has them filled. This repo builds on the database, so sector-filtered results differ slightly from running the original scripts against the CSVs.

**One extra sector.** The database carries a `Closed-End Fund` sector (four traded funds) and an `Unknown` sector (two sukuk ETFs) that the original 22-sector list did not. `Unknown` is excluded from the picker; `Closed-End Fund` is offered, giving 23 sectors.

**`indices_cleaned` is mostly repetition.** It was gap-filled to a complete 2014–2024 grid per company, so 1,752 of its 2,706 rows repeat the previous year verbatim. That is why the browser payload run-length encodes it: a bare year means "same values as before", and 2,706 rows compress to 954.

**One dividend row differs between sources.** Symbol 4349 has 2024 distributions in the loose `Divedend.csv` but not in the database. The database is the later snapshot and is what this repo uses.

**`dividend_ttm` for 4001 is `0.3399999999999999`.** That is what the source file contains — float drift baked in upstream, preserved rather than silently rounded.

## Precision in the browser payload

`tools/build_payload.py` stores capital, total liabilities and net income in millions with three decimals, so those three columns round to the nearest 1,000 SAR. Against values in the billions that is a rounding error well below the precision of the filings themselves.

Every other column is stored exactly. The parity test verifies all 24,354 indicator values decode back to their source.
