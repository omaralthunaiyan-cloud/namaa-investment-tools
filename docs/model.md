# Model card — annual close price predictor

Read this before quoting a number from the growth tool.

## What it is

A `RandomForestRegressor` (300 trees, median imputation, seed 42) that predicts a company's **average close price for a calendar year** from that year's fundamentals.

It is a regression on financial ratios, not a time-series model. It has no notion of momentum, no lagged prices, and no market-wide factor. Given a company's books and a year number, it returns a price.

## Training data

Rebuilt in pandas from `indices_cleaned` inner-joined to `yearly_prices_final` on symbol and year (the original scripts queried this as a database view, `v_model_base`; this repo has no live database, so `tools/train_model.py` reconstructs the same join). Only rows where a company has both a fundamentals record and a realised average price survive.

| | |
|---|---|
| Rows | 1,903 |
| Companies | 185 |
| Years | 2014–2024 |
| Features | year, capital, total_liabilities, net_income, roe, roa, pe, eps, bvps, de |
| Target | avg_close_price |

## Held-out performance

80/20 split, `random_state=42`, from the actual training run against the real data in this repo:

| Metric | Value |
|---|---|
| R² | 0.8511 |
| RMSE | 13.66 SAR |
| MAE | 7.78 SAR |

The final model is then refit on all 1,903 rows. (An earlier run, against an intermediate build of the same pipeline, produced R²=0.8437 / RMSE=13.26 / MAE=7.66 — close enough to the numbers above that the difference is noise from the train/test split and library versions, not a change in the data or method.)

An RMSE of ~14 SAR is not uniformly small. TASI prices in this set span roughly 5 to 300 SAR, so the same absolute error is a rounding difference for one company and a doubling for another. R² is flattered by the wide price range: predicting that expensive companies are expensive gets you most of the way there.

## How the 2025–2027 projections are produced

This is the part that matters most and is easiest to misread.

For each company, take its **most recent row** — latest fundamentals, whatever year that is — and copy it three times, changing only the `year` field to 2025, 2026, 2027. Predict on those rows.

So the projection answers: *what would the model price this company at in 2027, if its capital, liabilities, income and every ratio were exactly what they are today?*

Consequences worth stating plainly:

- **It is not a forecast.** Nothing about growth, guidance, or sector conditions enters. A company whose earnings are about to double looks identical to one whose earnings are flat.
- **Year contributes almost nothing.** With every other feature frozen, the only signal separating 2025 from 2027 is whatever the trees learned from `year` during training — which is largely a proxy for the general drift of the market, not for that company.
- **Large projected returns are usually artefacts.** The top of the ranking is dominated by companies whose last recorded average price was low relative to what their fundamentals imply. That gap is what the tool surfaces. Sometimes that is a genuinely mispriced company; often it is a data recency problem. In the live app, the top growth picks are routinely 100–350% projected ROI to 2027 — read that as a sign of the effect above, not as an expected return.
- **185 companies, not 270.** A company without both fundamentals and a price for the same year never enters training and never gets a projection.

## Where the linear model went

`reference/original/RGC.py` ranks companies using a `LinearRegression` with company fixed effects, persisted to a `predicted_roi` table. `reference/original/model_random_forest.py` says in its own docstring that the linear approach scored R² below zero and was dropped from the implementation.

The Growth tool keeps `RGC.py`'s allocation logic — equal weight across the top N, fractional shares — but feeds it Random Forest projections instead. This is a deliberate deviation, recorded here so nobody assumes the two files agree.

## Reproducing

```bash
pip install -r requirements.txt
python tools/train_model.py
```

Rewrites `data/predicted_prices_rf.csv` and `data/last_actual_prices.csv`, and `model_metrics.json`. Deterministic given the same data and seed (modulo minor floating-point differences across scikit-learn versions — see the two runs noted above). Follow with `python tools/build_payload.py` to push the new numbers into `web/data.js`.

## Intended use

Ranking and exploration. Screening a universe of 185 companies down to a shortlist worth reading filings about.

## Out of scope

Price targets, position sizing on real capital, anything with a time horizon, and any company outside the 185 in the training set.
