# Architecture

> **Design document.** This describes the pipeline the implementation is planned to follow. `tools/`, `engine/`, and `web/` don't exist in this repository yet — see the root [README](../README.md#status) for current status.

## The constraint that shaped everything

The original ran as a PostgreSQL database, a Flask API on `localhost:5000`, a Next.js dev server, and a handful of scripts with `C:\Users\Admin\Desktop\...` paths hardcoded in them. Four processes and a database to see a table of dividend recommendations.

The goal here was to make it open by double-clicking a file. That has one hard consequence: **no server means no query engine**, so all filtering, joining, scoring and combinatorial search has to happen in the browser, over data that ships with the page.

Everything below follows from that.

## Two implementations, one behaviour

```
                    tests/scenarios.json
                     /              \
              engine/ (Python)   web/src/App.jsx (JavaScript)
                     \              /
                   tests/test_parity.py
```

Python stays because retraining needs scikit-learn and pandas, and because scripting against the data should not require a browser. JavaScript exists because the browser build cannot call Python.

Duplicated logic drifts. The parity test is the answer: both implementations run the same scenario file, and 21 assertions compare recommendations, scores, month sets, formatted indicator values and allocation arithmetic. If someone fixes a bug on one side only, the suite goes red.

The model is deliberately *not* duplicated. Training writes `data/predicted_prices_rf.csv`; both sides read it.

## Build pipeline

```
Namaa_backup.dump
        │  tools/extract_dump.py          (pgdumplib, no server needed)
        ▼
    data/*.csv
        │
        ├──► engine/growth.py train()  ──► data/predicted_prices_rf.csv
        │                                            │
        └─────────────┬───────────────────────────┘
                       │  tools/build_payload.py
                       ▼
               web/src/data.js           (~108 KB)
                       │  web/build.mjs  (esbuild: bundle + minify + inline)
                       ▼
               web/index.html            (366 KB, zero external requests)
```

Two commands rebuild everything:

```bash
python tools/build_payload.py
cd web && npm run build
```

## Getting 270 companies into a page

The raw tables are around 630 KB of CSV. Three decisions cut the shipped payload to 108 KB:

**Reduce dividends to month sets.** Nothing at runtime reads an individual distribution — the two dividend tools only ask which months of 2024 a company paid in. So 1,258 rows become 137 lists.

**Run-length encode the fundamentals.** `indices_cleaned` was gap-filled, so 65% of rows repeat the year before verbatim. The blob format is `SYM:row|row|…;SYM:…` where a bare year means "same values again". 2,706 rows become 954, and the table drops from 202 KB to 72 KB.

**Trim numeric precision to what is displayed.** Money columns go to millions with three decimals; ratios keep four or five. The UI rounds to two decimals anyway.

Compare against the alternatives that were rejected: SQLite compiled to WebAssembly would have added roughly a megabyte of runtime to query 630 KB of data, and DuckDB-Wasm more. At this size a JavaScript array with a `Map` index is both smaller and faster.

## Why no Tailwind

The app was written with Tailwind utility classes. Shipping it meant either a build step, a CDN script tag, or the runtime compiler — the first two break "double-click to open" offline, and the third is 400 KB that runs on every page load.

`web/src/styles.css` is the ~130 utilities the app actually uses, written out by hand. Regenerate the list with:

```bash
grep -o 'className="[^"]*"' web/src/App.jsx | tr ' ' '\n' | sort -u
```

Colours never went through Tailwind in the first place — the design uses inline styles from a single `C` token object, because the palette is specific hex values rather than Tailwind's scale.

## Search cost

The dividend recommender is the only place where cost is a real question. All 128 payers across sizes 2 to 5 would be about 264 million combinations — fine in a background job, not fine on a click.

The original's answer, preserved here: shortlist the 25 best companies by `yield + 10 × months_covered`, then enumerate within those. That is at most 245,480 combinations for the full 2–6 range, which the browser scores in well under a second.

The shortlist is a real approximation. A company ranked 26th on the heuristic can never appear in a recommendation, even if it would complete a portfolio's calendar perfectly. That is a property of the original algorithm and was left alone; changing it would change every recommendation the project has ever produced.

## State

No router, no state library. `NamaaApp` holds a single `page` string and each tool page holds its own inputs in `useState`. Results are computed in `useMemo` against a submitted request object rather than against the live inputs, so moving a slider does not recompute a 245,000-combination search on every frame.

No `localStorage`, no persistence, no network calls of any kind. Opening the file is the whole lifecycle.
