"""
model_random_forest.py

- Reads v_model_base from PostgreSQL
- Trains a Random Forest Regressor to predict avg_close_price
- Evaluates it with R², RMSE, MAE
- Predicts future prices for 2025–2027 using the latest indicators per company
- Joins predictions with companies table (company_name, sector)
- Saves:
    - predicted_prices_rf.csv
    - top5_rf_latest_year.csv

Note:
Linear Regression was tried conceptually (for the report) but not kept in code
because its performance was very poor (R² < 0). Random Forest is used as the
main model in implementation.
"""

import numpy as np
import pandas as pd
from sqlalchemy import create_engine, text

from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from sklearn.ensemble import RandomForestRegressor


# -----------------------------------------------------------------------------
# 1) CONFIG: DATABASE CONNECTION
# -----------------------------------------------------------------------------
DB_USER = "postgres"
DB_PASSWORD = "REDACTED"  # original hardcoded a local dev password here; removed before publishing
DB_HOST = "localhost"
DB_PORT = "5432"
DB_NAME = "Namaa"  # change if your DB name is different

DB_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"


# -----------------------------------------------------------------------------
# 2) DATA LOADING FUNCTIONS
# -----------------------------------------------------------------------------
def load_v_model_base(engine):
    """
    Load the main modeling view from PostgreSQL.
    v_model_base has:
      base_symbol, year, capital, total_liabilities, net_income,
      roe, roa, pe, eps, bvps, de, avg_close_price
    """
    print("[INFO] Loading v_model_base ...")
    query = text("""
        SELECT
            base_symbol,
            year,
            capital,
            total_liabilities,
            net_income,
            roe,
            roa,
            pe,
            eps,
            bvps,
            de,
            avg_close_price
        FROM public.v_model_base
        ORDER BY base_symbol, year;
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    print(f"[INFO] Loaded {len(df):,} rows from v_model_base.")
    return df


def load_companies(engine):
    """
    Load companies table to attach company_name and sector to predictions.
    companies has:
      symbol (matches base_symbol), company_name, sector
    """
    print("[INFO] Loading companies ...")
    query = text("""
        SELECT
            symbol,
            company_name,
            sector
        FROM public.companies;
    """)
    with engine.connect() as conn:
        df = pd.read_sql(query, conn)

    print(f"[INFO] Loaded {len(df):,} rows from companies.")
    return df


# -----------------------------------------------------------------------------
# 3) TRAINING & EVALUATION
# -----------------------------------------------------------------------------
def train_random_forest(df):
    """
    Train a Random Forest Regressor on v_model_base data.

    Features:
      year, capital, total_liabilities, net_income, roe, roa, pe, eps, bvps, de
    Target:
      avg_close_price

    Returns:
      - fitted_model
      - full feature DataFrame X (all rows)
      - target Series y (all rows)
    """
    # Ensure year is integer
    df["year"] = df["year"].astype(int)

    feature_cols = [
        "year",
        "capital",
        "total_liabilities",
        "net_income",
        "roe",
        "roa",
        "pe",
        "eps",
        "bvps",
        "de",
    ]
    target_col = "avg_close_price"

    X = df[feature_cols]
    y = df[target_col]

    # Split for evaluation (we still use all data later for final training)
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print(f"[INFO] Training rows: {len(X_train):,}, Test rows: {len(X_test):,}")

    # Random Forest pipeline with imputer
    rf_pipeline = Pipeline(steps=[
        ("imputer", SimpleImputer(strategy="median")),
        ("model", RandomForestRegressor(
            n_estimators=300,
            random_state=42,
            n_jobs=-1
        ))
    ])

    print("[INFO] Training Random Forest model ...")
    rf_pipeline.fit(X_train, y_train)

    # Evaluate on test set
    y_pred = rf_pipeline.predict(X_test)
    r2 = r2_score(y_test, y_pred)
    mse = mean_squared_error(y_test, y_pred)
    rmse = np.sqrt(mse)
    mae = mean_absolute_error(y_test, y_pred)

    print(f"[RESULT] Random Forest Performance on Test Set:")
    print(f"         R²   = {r2:.4f}")
    print(f"         RMSE = {rmse:.4f}")
    print(f"         MAE  = {mae:.4f}")

    # Optionally retrain on all data for final model
    print("[INFO] Retraining Random Forest on ALL data for final model ...")
    rf_pipeline.fit(X, y)

    return rf_pipeline, X, y, feature_cols


# -----------------------------------------------------------------------------
# 4) FUTURE FEATURE GENERATION (2025–2027)
# -----------------------------------------------------------------------------
def build_future_features(df_all, feature_cols, future_years=(2025, 2026, 2027)):
    """
    For each company (base_symbol), take its latest available financial row,
    and create copies for each future year (2025–2027).

    This assumes the financial profile stays similar and only the year changes.
    """
    df_sorted = df_all.sort_values(["base_symbol", "year"])
    latest_per_symbol = df_sorted.groupby("base_symbol").tail(1).reset_index(drop=True)

    print(f"[INFO] Latest snapshot per company: {len(latest_per_symbol):,} companies")

    future_rows = []

    for _, row in latest_per_symbol.iterrows():
        for year in future_years:
            new_row = row.copy()
            new_row["year"] = year
            future_rows.append(new_row)

    future_df = pd.DataFrame(future_rows)

    # Keep only required feature columns + base_symbol + year
    future_features = future_df[["base_symbol", "year"] + feature_cols[1:]]  # year + financials
    return future_features


# -----------------------------------------------------------------------------
# 5) PREDICTIONS & RECOMMENDATIONS
# -----------------------------------------------------------------------------
def make_predictions(model, df_all, df_companies, feature_cols,
                     future_years=(2025, 2026, 2027),
                     output_predictions_path="predicted_prices_rf.csv",
                     output_top5_path="top5_rf_latest_year.csv"):
    """
    Use the trained Random Forest model to predict prices for future years,
    then join with company_name and sector, and save:

      - predicted_prices_rf.csv : all companies x future years
      - top5_rf_latest_year.csv : top 5 companies in the last future year

    Returns:
      - predictions_df : full prediction DataFrame
      - top5_df        : top 5 recommendations for latest year
    """
    future_features = build_future_features(df_all, feature_cols, future_years)
    X_future = future_features[feature_cols]

    # Predict
    future_features["predicted_price_rf"] = model.predict(X_future)

    # Join with company info
    merged = future_features.merge(
        df_companies,
        left_on="base_symbol",
        right_on="symbol",
        how="left"
    )

    # Reorder columns
    merged = merged[[
        "base_symbol",
        "company_name",
        "sector",
        "year",
        "predicted_price_rf"
    ]]

    # Save all predictions
    merged.sort_values(["year", "predicted_price_rf"], ascending=[True, False], inplace=True)
    merged.to_csv(output_predictions_path, index=False, encoding="utf-8-sig")
    print(f"[INFO] Saved all future predictions to {output_predictions_path} (rows={len(merged):,})")

    # Top 5 for latest year
    latest_year = max(future_years)
    latest_df = merged[merged["year"] == latest_year].copy()
    top5 = latest_df.sort_values("predicted_price_rf", ascending=False).head(5)
    top5.to_csv(output_top5_path, index=False, encoding="utf-8-sig")
    print(f"[INFO] Saved Top 5 recommendations for {latest_year} to {output_top5_path}")

    print("\n[TOP 5 RECOMMENDATIONS]")
    print(top5)

    return merged, top5


# -----------------------------------------------------------------------------
# 6) MAIN FUNCTION
# -----------------------------------------------------------------------------
def main():
    # Connect to DB
    engine = create_engine(DB_URL)

    # Load data
    df_model = load_v_model_base(engine)
    df_companies = load_companies(engine)

    # Train Random Forest
    model, X, y, feature_cols = train_random_forest(df_model)

    # Predict future prices and save CSVs
    make_predictions(
        model,
        df_model,
        df_companies,
        feature_cols,
        future_years=(2025, 2026, 2027),
        output_predictions_path="predicted_prices_rf.csv",
        output_top5_path="top5_rf_latest_year.csv"
    )


if __name__ == "__main__":
    main()
