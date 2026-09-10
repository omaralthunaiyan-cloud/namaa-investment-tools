# Reference

`original/` holds the IS499 scripts exactly as they were written, so the browser build and the `tools/` pipeline can be checked against their source. One line was redacted in two files before publishing: a hardcoded local PostgreSQL password (`DB_PASSWORD` in `model_random_forest.py`, and inline in `RGC.py`'s connection string). Nothing else was changed.

| File | Ported to |
|---|---|
| `RDC_V5_UI.py` | `web/index.html`'s "Recommend Dividend Companies" tool |
| `CByDM.py` | `web/index.html`'s "Get Companies by Dividend Months" tool |
| `CodeForIndices.py` | `web/index.html`'s "Get Indices for a Company" tool |
| `RGC.py` | allocation logic only (equal-weight, fractional shares) — the ranking now comes from the Random Forest instead of `RGC.py`'s linear regression, see [`docs/model.md`](../docs/model.md) |
| `model_random_forest.py` | `tools/train_model.py` |
| `streamlit_app.py` | superseded by `web/index.html` |

These files are kept for provenance and are not imported by anything. They won't run as-is: they read Windows desktop paths and connect to a local PostgreSQL instance.
