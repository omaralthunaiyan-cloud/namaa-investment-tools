"""
Train the Random Forest growth model on data/*.csv and write
data/predicted_prices_rf.csv + data/last_actual_prices.csv.

Mirrors reference/original/model_random_forest.py, but reads the CSVs in
data/ (produced by tools/extract_dump.py) instead of querying PostgreSQL's
v_model_base view directly — v_model_base is `indices_cleaned` INNER JOINed
to `yearly_prices_final` on symbol + year, reconstructed here in pandas.

Usage:
    pip install -r requirements.txt
    python tools/train_model.py
"""
import json
import re

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

DATA = "data"
FEATURE_COLS = ["year", "capital", "total_liabilities", "net_income", "roe", "roa", "pe", "eps", "bvps", "de"]
FUTURE_YEARS = [2025, 2026, 2027]


def base_symbol(s):
    return re.sub(r"\.SR$", "", str(s))


def main():
    indices_cleaned = pd.read_csv(f"{DATA}/indices_cleaned.csv")
    indices_cleaned["symbol"] = indices_cleaned["symbol"].apply(base_symbol)

    yearly_prices_final = pd.read_csv(f"{DATA}/yearly_prices_final.csv")
    yearly_prices_final = yearly_prices_final.rename(columns={"base_symbol": "symbol"})
    yearly_prices_final["symbol"] = yearly_prices_final["symbol"].apply(base_symbol)

    # v_model_base: indices_cleaned INNER JOIN yearly_prices_final on symbol+year
    model_base = indices_cleaned.merge(yearly_prices_final, on=["symbol", "year"], how="inner")
    print(f"[INFO] v_model_base: {len(model_base)} rows, {model_base['symbol'].nunique()} companies")

    X = model_base[FEATURE_COLS]
    y = model_base["avg_close_price"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    pipeline = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("model", RandomForestRegressor(n_estimators=300, random_state=42, n_jobs=-1)),
    ])
    pipeline.fit(X_train, y_train)
    y_pred = pipeline.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    rmse = float(np.sqrt(mean_squared_error(y_test, y_pred)))
    mae = float(mean_absolute_error(y_test, y_pred))
    print(f"[RESULT] R2={r2:.4f} RMSE={rmse:.4f} MAE={mae:.4f}")

    # Refit on all data for the final model (matches the original script)
    pipeline.fit(X, y)

    # Future rows: latest fundamentals per company, year swapped to 2025-2027
    latest_per_symbol = model_base.sort_values(["symbol", "year"]).groupby("symbol").tail(1)
    future_rows = []
    for _, row in latest_per_symbol.iterrows():
        for yr in FUTURE_YEARS:
            r = row.copy()
            r["year"] = yr
            future_rows.append(r)
    future_df = pd.DataFrame(future_rows)
    future_df["predicted_price_rf"] = pipeline.predict(future_df[FEATURE_COLS])

    future_df[["symbol", "year", "predicted_price_rf"]].to_csv(f"{DATA}/predicted_prices_rf.csv", index=False)

    last_actual = (model_base.sort_values(["symbol", "year"]).groupby("symbol").tail(1)
                   [["symbol", "year", "avg_close_price"]]
                   .rename(columns={"year": "last_year", "avg_close_price": "last_price"}))
    last_actual.to_csv(f"{DATA}/last_actual_prices.csv", index=False)

    with open("model_metrics.json", "w") as f:
        json.dump({
            "r2": r2, "rmse": rmse, "mae": mae,
            "train_rows": len(X_train), "test_rows": len(X_test),
            "model_base_rows": len(model_base),
            "model_base_companies": int(model_base["symbol"].nunique()),
        }, f, indent=2)

    print(f"[INFO] wrote {DATA}/predicted_prices_rf.csv, {DATA}/last_actual_prices.csv, model_metrics.json")


if __name__ == "__main__":
    main()
