# Architecture

## The constraint that shaped everything

The original ran as a PostgreSQL database, a Flask API on `localhost:5000`, a Next.js dev server, and a handful of scripts with `C:\Users\Admin\Desktop\...` paths hardcoded in them. Four processes and a database to see a table of dividend recommendations.

The goal here was to make it open with no install — a link, or double-clicking a file. That has one hard consequence: **no server means no query engine**, so all filtering, joining, scoring and combinatorial search has to happen in the browser, over data that ships with the page.

Everything below follows from that.

## One implementation

Unlike the original plan sketched early in this project (a Python `engine/` package mirrored by JavaScript, cross-checked by a parity test suite), the logic that ships lives in exactly one place: `web/index.html`'s JavaScript, ported by hand from each script in [`reference/original/`](../reference/original/). There's a real cost to that — nothing currently catches the two implementations drifting, because there's only one. The upside is there's nothing to keep in sync, and one working implementation beats two partial ones. Reintroducing a Python `engine/` (for CLI scripting, retraining, and a parity test against the JS) is on the list of things worth doing next, not something this doc pretends already exists.

`tools/train_model.py` is the one place Python still does real work — retraining needs scikit-learn and pandas, and training in the browser isn't worth it. It writes `data/predicted_prices_rf.csv`; the browser build reads that.

## Build pipeline

```
Namaa_backup.dump
        │  tools/extract_dump.py          (pgdumplib, no server needed)
        ▼
    data/*.csv
        │
        ├──► tools/train_model.py  ──► data/predicted_prices_rf.csv
        │                                            │
        └─────────────┬───────────────────────────┘
                       │  tools/build_payload.py
                       ▼
               web/data.js                (~110 KB)
                       │  (read directly by a <script> tag — no bundler)
                       ▼
               web/index.html             (reads window.NAMAA_DATA, zero external requests)
```

Four commands rebuild everything from the dump — see the root README's [Reproducing the build](../README.md#reproducing-the-build).

## Getting 270 companies into a page

The raw tables are several hundred KB of CSV. Two decisions keep the shipped payload (`web/data.js`) around 110 KB:

**Reduce dividends to month sets.** Nothing at runtime reads an individual distribution — the two dividend tools only ask which months of 2024 a company paid in. So 1,258 rows become month lists per symbol.

**Run-length encode the fundamentals.** `indices_cleaned` was gap-filled, so 1,752 of its 2,706 rows repeat the year before verbatim. The payload stores one entry per (symbol, year): either the full row, or a bare year meaning "same values as the entry before it." See [`docs/data.md`](data.md) for the exact numbers.

A JavaScript object with the decompressed-on-read data is both simpler and smaller than shipping a WASM SQL engine (SQLite-in-WASM or DuckDB-WASM) to query a dataset this size.

## Styling

Hand-written CSS in a `<style>` block, no framework, no build step — light and dark palettes via `prefers-color-scheme`. No Tailwind, no CDN font or script of any kind: the page has to work offline and open with nothing but a browser.

## Search cost

The dividend recommender is the only place where cost is a real question. All 128 payers across sizes 2 to 8 would be tens of millions of combinations — fine in a background job, not fine on a click.

The original's answer, kept exactly: shortlist the 25 best companies by `yield + 10 × months_covered`, then enumerate combinations within that shortlist only. The browser scores tens of thousands of combinations in well under a second this way.

The shortlist is a real approximation. A company ranked 26th on the heuristic can never appear in a recommendation, even if it would complete a portfolio's calendar perfectly. That's a property of the original algorithm, kept deliberately — changing it would change every recommendation the tool has ever produced.

## State

No router, no framework. Plain DOM manipulation from vanilla JavaScript; each tool's inputs and results live in module-level variables, recomputed only when its "Generate" / "Search" / "Show" button is clicked — not on every keystroke.

No `localStorage`, no persistence, no network calls of any kind. Opening the page is the whole lifecycle.
