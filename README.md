# Namaa

Four decision tools for Tadawul-listed companies: which dividend payers to hold, when they pay, what their fundamentals look like, and which companies a model ranks highest for growth.

Namaa started as an IS499 senior project — PostgreSQL, a pile of Python scripts, a Streamlit page, and a separate Next.js prototype that talked to a Flask API. This repository is that work reorganised so it actually runs somewhere other than the machine it was written on.

**The whole thing opens in a browser with no install.** Download [`web/index.html`](web/index.html) and double-click it. No Python, no Node, no database, no network. One 366 KB file with React, the four algorithms, and 270 companies' worth of data inside it.

---

## Quick start

### Just use it

```
open web/index.html
```

That's the entire instruction. It also works as a GitHub Pages site — point Pages at the `web/` folder and it deploys as-is.

### Use it from a terminal

```bash
pip install -r requirements.txt

python -m engine.cli dividends --amount 10000 --coverage 50 --companies 3
python -m engine.cli months 3 6 9 12
python -m engine.cli indices 2222 --years 2022 2023 2024
python -m engine.cli growth --amount 15000 --top 5 --year 2027
```

```
Option 1   score 29.4
  symbol  name                    amount
  ------  ----------------------  -------
  7010    Saudi Telecom Co.       3333.33
  4190    Jarir Marketing Co.     3333.33
  4003    United Electronics Co.  3333.33
  coverage 50.0%   average profit 8.79%   months [3, 5, 6, 8, 11, 12]
```

### Rebuild it

```bash
python tools/build_payload.py     # data/*.csv  ->  web/src/data.js
cd web && npm install && npm run build   # -> web/index.html
```

---

## The four tools

### Recommend Dividend Companies

You give it an amount, a split between *coverage* and *profit*, and optionally some sectors. It returns three portfolios.

Profit is trailing dividend over reference close price. Coverage is how many distinct months of the year the portfolio pays in — a portfolio's coverage is the union of its members' payout months, so two companies that both pay only in March cover one month between them, while two that pay in March and September cover two.

The interesting part is that coverage is scored on *closeness to a target*, not on maximisation. Asking for 50% coverage means "about six months", and a portfolio covering nine months scores worse than one covering six. That is what makes the slider a real preference rather than a dial that only goes one way.

Search is not exhaustive. All 128 payers would give C(128,5) ≈ 264 million combinations, so the original shortlists the 25 best by `yield + 10 × months_covered` and enumerates within those. The heuristic is preserved exactly — changing it would change the answers.

### Get Companies by Dividend Months

Stricter than it looks. Asking for March does not return everything that paid in March; it returns companies whose *entire* year was March. Asking for March and September returns companies whose year was exactly those two months.

That is the right rule for the job. If you are assembling a payout calendar, a company that also pays in June is putting money in your account in a month you did not plan for. When nothing matches an exact combination the tool falls back to picking the strongest single-month payer for each month separately, which builds the same calendar out of several companies. The result tells you which of the three branches fired, because that changes how you read it.

### Get Indices for a Company

Nine annual fundamentals — capital, total liabilities, net income, ROE, ROA, EPS, P/E, BVPS, D/E — for 246 companies across 2014-2024. Search by symbol or by partial name.

Read the repeated rows carefully. The source table was gap-filled, so a company with two reporting years still shows eleven rows and the gaps carry the nearest known values forward or backward. A repeated row means "no new filing", not "no change in the business". About 65% of rows are carried-forward duplicates, which is also why the whole table compresses from 202 KB to 72 KB in the browser build.

### Recommend Growth Companies

A Random Forest predicts each company's average annual close price for 2025-2027 from its most recent fundamentals. Companies are ranked by projected return, and your capital is split equally across the top of that ranking.

See [`docs/model.md`](docs/model.md) before trusting a number from this one. The short version: held-out R² is 0.844, but future rows are built by taking each company's latest financials and only changing the year. The model answers "what would this be worth if the books stayed exactly as they are", which is a ranking signal, not a forecast.

---

## How it fits together

```
Namaa_backup.dump  (PostgreSQL 17, custom format)
        |
        |  tools/extract_dump.py
        v
    data/*.csv  ──────────────────────────┐
        |                                 |
        |  engine/growth.py train()       |  tools/build_payload.py
        v                                 v
  predicted_prices_rf.csv           web/src/data.js
        |                                 |
        └──────> engine/  (Python)        |  web/build.mjs
                    |                     v
                    |               web/index.html
                    |                     |
                    └── tests/test_parity.py ──┘
```

Every algorithm exists twice: once in `engine/` for scripting and retraining, once in JavaScript so the browser build needs no server. Two implementations of the same thing drift, so `tests/test_parity.py` runs both over a shared scenario file and compares them field by field. 21 tests, all green.

The model is the one thing that does *not* exist twice. Training needs scikit-learn; shipping scikit-learn to a browser is not worth it. So training writes a CSV of projections and both sides read that.

---

## Layout

```
data/                CSVs extracted from the database dump
engine/              the four tools as importable Python
  data.py            loading and symbol normalisation
  dividends.py       Recommend Dividend Companies
  schedule.py        Get Companies by Dividend Months
  indices.py         Get Indices for a Company
  growth.py          Random Forest training + capital allocation
  cli.py             command line front end
web/
  index.html         built, self-contained, no dependencies
  src/App.jsx        the app
  src/data.js        generated payload — do not edit
  src/styles.css     hand-written CSS, no Tailwind build step
  build.mjs          produces index.html
  golden.mjs         produces the parity fixtures
tools/
  extract_dump.py    dump -> CSVs
  build_payload.py   CSVs -> web/src/data.js
tests/
  scenarios.json     shared inputs for both implementations
  test_parity.py     Python vs JavaScript
docs/                architecture, data provenance, model card
reference/original/  the untouched IS499 scripts, for provenance
```

---

## Data

Everything traces back to `Namaa_backup.dump`, a PostgreSQL 17 custom-format dump. Note that `pg_restore` before version 17 rejects it — `tools/extract_dump.py` reads it directly with `pgdumplib`, so you never need a running database.

| Table | Rows | Used for |
|---|---:|---|
| `companies` | 270 | names and sectors everywhere |
| `dividend_ttm` | 128 | the payer universe and profit yield |
| `dividends` | 1,258 | payout calendar, 2020-2026 |
| `indices_cleaned` | 2,706 | fundamentals, 2014-2024, gap-filled |
| `yearly_prices_final` | 2,528 | the model's training target |
| `historical_prices` | 272,235 | source of the yearly averages; not shipped |

`historical_prices` is excluded from `data/` because it is 9 MB and nothing reads it at runtime. Recover it with `python tools/extract_dump.py Namaa_backup.dump --all`.

See [`docs/data.md`](docs/data.md) for column-level notes and the known quirks.

---

## Things that were broken, and are now not

Worth recording, because two of these silently returned empty results rather than failing.

**Three sectors in the web prototype had names the database never used.** The UI offered `Commercial & Professional Services`, `Health Care Equipment & Services` and `Real Estate Management & Development`; the data stores `Svc`, `Svc` and `Mgmt & Dev't`. Selecting any of them filtered the universe to nothing and returned no recommendations, with no error. The UI labels are now mapped to the stored spellings.

**Eleven companies had a blank sector in `Companies.csv`.** The database has them filled in. Building on the database rather than the CSVs picks up all eleven, which changes sector-filtered results slightly compared to running the original scripts.

**The generate button accepted an investment amount of zero** and navigated to a results page that divided by it. It now validates.

**`Preview Inputs` only called `console.log`.** It now shows the inputs.

**`RGC.py` ranked on a linear regression** persisted to a `predicted_roi` table, while `model_random_forest.py` states in its own docstring that the linear model scored below zero R² and was dropped. The allocation logic here is fed by the Random Forest instead. This is a deliberate deviation from RGC.py, not a port of it.

---

## Testing

```bash
python -m pytest tests/ -v          # 21 parity tests
cd web && npm run golden            # regenerate the JavaScript fixtures
```

One difference between the two implementations is known and encoded in the test: when several companies share an identical trailing dividend, the calendar search may order them differently. Both sides sort by dividend descending, both are stable, but they stabilise against different source orderings. The result set and the dividend ranking are identical, so the comparison is order-insensitive within a month.

---

## Not investment advice

Every number here comes from historical filings and a model trained on 185 companies. The growth tool in particular projects prices by holding each company's financials constant and moving the year forward, which produces large returns for companies whose last recorded price was unusually low. Treat the output as a ranking signal and check anything before acting on it.
