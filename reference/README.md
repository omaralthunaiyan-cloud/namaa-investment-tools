# Reference

`original/` holds the IS499 scripts exactly as they were written, so the ports
in `engine/` and `web/src/App.jsx` can be checked against their source.

| File | Ported to |
|---|---|
| `RDC_V5_UI.py` | `engine/dividends.py`, `recommendDividendCompanies` |
| `CByDM.py` | `engine/schedule.py`, `companiesByDividendMonths` |
| `CodeForIndices.py` | `engine/indices.py`, `getCompanyIndices` |
| `RGC.py` | `engine/growth.py` `plan()` — allocation only, see `docs/model.md` |
| `model_random_forest.py` | `engine/growth.py` `train()` |
| `streamlit_app.py` | superseded by `web/` and `engine/cli.py` |

These files are kept for provenance and are not imported by anything. They will
not run as-is: they read Windows desktop paths and connect to a local
PostgreSQL instance with credentials in the source.
