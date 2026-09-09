# Namaa

Four decision tools for Tadawul-listed companies: which dividend payers to hold, when they pay, what their fundamentals look like, and which companies a model ranks highest for growth.

![status](https://img.shields.io/badge/status-architecture%20%26%20spec-orange) ![python](https://img.shields.io/badge/planned-Python%20%2B%20React-3776AB) ![license](https://img.shields.io/badge/license-unpublished-lightgrey)

Namaa started as an IS499 senior project — PostgreSQL, a pile of Python scripts, a Streamlit page, and a separate Next.js prototype that talked to a Flask API. This repository is the plan for turning that into something that runs somewhere other than the machine it was written on: a single browser file with no install, plus a scriptable Python engine behind it.

---

## Contents

- [Status](#status)
- [The four tools](#the-four-tools)
- [Planned architecture](#planned-architecture)
- [Data](#data)
- [Issues in the original scripts, and how the port fixes them](#issues-in-the-original-scripts-and-how-the-port-fixes-them)
- [Target layout](#target-layout)
- [Roadmap](#roadmap)
- [Not investment advice](#not-investment-advice)

---

## Status

**This repository is documentation and architecture, not yet an implementation.** Everything below — the four tools, the build pipeline, the data model, the model card — is the finished design. None of `engine/`, `web/`, `tools/`, `tests/`, or the CSVs in `data/` has been written or committed here yet.

| Piece | State |
|---|---|
| Product spec — what each tool does and why | done, below |
| Architecture — how data flows from dump to browser | designed, [`docs/architecture.md`](docs/architecture.md) |
| Data model and quirks | documented, [`docs/data.md`](docs/data.md) |
| Model card | written, [`docs/model.md`](docs/model.md) |
| `engine/` (Python) | not started |
| `web/` (React build) | not started |
| `tools/` (dump → CSV → payload) | not started |
| `tests/` (parity suite) | not started |
| Original IS499 scripts in `reference/original/` | not yet committed |

If you're reading this from a job application or a portfolio link: this is the design phase of the rebuild, done properly before writing code against it. See [Roadmap](#roadmap) for what's next.

---

## The four tools

### Recommend Dividend Companies

You give it an amount, a split between *coverage* and *profit*, and optionally some sectors. It returns three portfolios.

Profit is trailing dividend over reference close price. Coverage is how many distinct months of the year the portfolio pays in — a portfolio's coverage is the union of its members' payout months, so two companies that both pay only in March cover one month between them, while two that pay in March and September cover two.

The interesting part is that coverage is scored on *closeness to a target*, not on maximisation. Asking for 50% coverage means "about six months," and a portfolio covering nine months scores worse than one covering six. That is what makes the slider a real preference rather than a dial that only goes one way.

Search is not exhaustive. All 128 payers would give C(128,5) ≈ 264 million combinations, so the design shortlists the 25 best by `yield + 10 × months_covered` and enumerates within those. The heuristic is carried over from the original scripts deliberately — changing it would change the answers.

### Get Companies by Dividend Months

Stricter than it looks. Asking for March should not return everything that paid in March; it should return companies whose *entire* year was March. Asking for March and September should return companies whose year was exactly those two months.

That is the right rule for the job. If you are assembling a payout calendar, a company that also pays in June is putting money in your account in a month you did not plan for. When nothing matches an exact combination, the design falls back to picking the strongest single-month payer for each month separately, which builds the same calendar out of several companies. The result should say which of the three branches fired, because that changes how you read it.

### Get Indices for a Company

Nine annual fundamentals — capital, total liabilities, net income, ROE, ROA, EPS, P/E, BVPS, D/E — for 246 companies across 2014–2024. Search by symbol or by partial name.

The source table is gap-filled, so a company with two reporting years still shows eleven rows and the gaps carry the nearest known values forward or backward. A repeated row means "no new filing," not "no change in the business." About 65% of rows are carried-forward duplicates — see [Data](#data) for how that's planned to compress in the browser build.

### Recommend Growth Companies

A Random Forest predicts each company's average annual close price for 2025–2027 from its most recent fundamentals. Companies are ranked by projected return, and capital is split equally across the top of that ranking.

Read [`docs/model.md`](docs/model.md) before trusting a number from this one. The short version: held-out R² is 0.844, but future rows are built by taking each company's latest financials and only changing the year. The model answers "what would this be worth if the books stayed exactly as they are," which is a ranking signal, not a forecast.

---

## Planned architecture

Full detail in [`docs/architecture.md`](docs/architecture.md). The short version:

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

Every algorithm is designed to exist twice: once in `engine/` for scripting and retraining, once in JavaScript so the browser build needs no server. Two implementations of the same thing drift, so `tests/test_parity.py` is planned to run both over a shared scenario file and compare them field by field.

The model is the one thing that will **not** exist twice. Training needs scikit-learn; shipping scikit-learn to a browser is not worth it. Training will write a CSV of projections and both sides will read that.

**No server means no query engine.** The whole point of a double-click, no-install file is that all filtering, joining, scoring, and combinatorial search has to happen in the browser, over data that ships with the page — see `docs/architecture.md` for how the planned payload gets 270 companies down to roughly 108 KB.

---

## Data

Full detail in [`docs/data.md`](docs/data.md). Everything traces back to `Namaa_backup.dump`, a PostgreSQL 17 custom-format dump — note `pg_restore` before version 17 rejects it, which is why `tools/extract_dump.py` is designed to read it directly with `pgdumplib` rather than requiring a running database.

| Table | Rows | Used for |
|---|---:|---|
| `companies` | 270 | names and sectors everywhere |
| `dividend_ttm` | 128 | the payer universe and profit yield |
| `dividends` | 1,258 | payout calendar, 2020–2026 |
| `indices_cleaned` | 2,706 | fundamentals, 2014–2024, gap-filled |
| `yearly_prices_final` | 2,528 | the model's training target |
| `historical_prices` | 272,235 | source of the yearly averages; not planned to ship |

`historical_prices` is planned to stay out of `data/` because it's 9 MB and nothing reads it at runtime.

---

## Issues in the original scripts, and how the port fixes them

Found while reading `reference/original/` closely. Recorded here so the port addresses them rather than carrying them forward silently — two of these returned empty results with no error, which is the kind of bug that's easy to miss.

**Three sectors had names the database never used.** The UI offered `Commercial & Professional Services`, `Health Care Equipment & Services`, and `Real Estate Management & Development`; the data stores `Svc`, `Svc`, and `Mgmt & Dev't`. Selecting any of them filtered the universe to nothing. Fix: map the UI labels to the stored spellings.

**Eleven companies have a blank sector in `Companies.csv`.** The database has them filled in. Fix: build on the database rather than the loose CSVs, which also changes sector-filtered results slightly versus the original scripts.

**The generate button accepted an investment amount of zero,** which then divided by it downstream. Fix: validate before submitting.

**`Preview Inputs` only called `console.log`.** Fix: actually show the inputs in the UI.

**`RGC.py` ranks on a linear regression** persisted to a `predicted_roi` table, while `model_random_forest.py`'s own docstring says the linear model scored below zero R² and was dropped. Fix: feed RGC's allocation logic with Random Forest projections instead — a deliberate deviation from `RGC.py`, not a straight port of it. Detail in [`docs/model.md`](docs/model.md).

---

## Target layout

What the repository is designed to look like once the port is written:

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
  src/data.js        generated payload — not hand-edited
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

## Roadmap

- [ ] Commit the original IS499 scripts to `reference/original/` for provenance
- [ ] `tools/extract_dump.py` — pull `data/*.csv` out of `Namaa_backup.dump`
- [ ] `engine/` — port the four tools to importable Python, plus `cli.py`
- [ ] `engine/growth.py train()` — retrain the Random Forest, write `data/predicted_prices_rf.csv`
- [ ] `tools/build_payload.py` — compress the CSVs into `web/src/data.js`
- [ ] `web/` — the React app and the esbuild pipeline that inlines it into one `index.html`
- [ ] `tests/test_parity.py` — Python vs. JavaScript, scenario by scenario
- [ ] Publish `web/index.html` via GitHub Pages

---

## Not investment advice

Every number here comes from historical filings and a model trained on 185 companies. The growth tool in particular is designed to project prices by holding each company's financials constant and moving the year forward, which produces large returns for companies whose last recorded price was unusually low. Once built, its output should be treated as a ranking signal, checked against real filings before anyone acts on it.
