import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler

# ----------------------------
# DB connection (EDIT)
# ----------------------------
ENGINE = create_engine("postgresql+psycopg2://postgres:REDACTED@localhost/Namaa")  # original hardcoded a local dev password here; removed before publishing

# ----------------------------
# TRAIN + STORE PREDICTIONS
# ----------------------------
def train_and_store_predictions():
    import pandas as pd, numpy as np
    from sqlalchemy import text
    from sklearn.linear_model import LinearRegression
    from sklearn.preprocessing import StandardScaler

    # 1) Load panel data
    panel_q = """
    SELECT f.symbol,
           f.year::int AS year,
           p.avg_close_price,
           f.capital, f.total_liabilities, f.net_income,
           f.roe, f.roa, f.pe, f.eps, f.bvps, f.de, f.earnings_yield
    FROM indices_features f
    JOIN v_yearly_prices p
      ON p.symbol = f.symbol AND p.year = f.year
    ORDER BY f.symbol, f.year;
    """
    panel = pd.read_sql(panel_q, ENGINE).sort_values(["symbol","year"]).reset_index(drop=True)
    print(f"[DEBUG] panel rows={len(panel)}, symbols={panel['symbol'].nunique()}, years={panel['year'].nunique()}")

    if panel.empty:
        raise SystemExit("Joined panel is empty. Check that v_yearly_prices and indices_features have overlapping years.")

    # 2) Fill within symbol
    feat_cols = ["capital","total_liabilities","net_income","roe","roa","pe","eps","bvps","de","earnings_yield"]
    panel[feat_cols] = (
        panel.groupby("symbol")[feat_cols]
             .apply(lambda g: g.ffill().bfill())
             .reset_index(level=0, drop=True)
    )

    # Impute earnings_yield if still missing → use global median (robust)
    if panel["earnings_yield"].isna().any():
        ey_median = panel["earnings_yield"].median(skipna=True)
        panel["earnings_yield"] = panel["earnings_yield"].fillna(ey_median)
        print(f"[DEBUG] Filled missing earnings_yield with median={ey_median:.6f}")

    # 3) Build training
    feature_cols_numeric = ["year"] + feat_cols
    train = panel.dropna(subset=["avg_close_price"]).dropna(subset=feature_cols_numeric).copy()
    print(f"[DEBUG] train rows={len(train)}, symbols={train['symbol'].nunique()}, years={train['year'].nunique()}")

    # If still too small, FALLBACK to per-company Year→Price regression (no indices)
    if train["year"].nunique() < 3:
        print("[WARN] <3 distinct years in training. Falling back to per-company Year→Price regression.")
        return _fallback_year_only(panel)

    # 4) Fixed effects via one-hot (ok if only 1 symbol → no dummy columns)
    dummies = pd.get_dummies(train["symbol"], prefix="sym", drop_first=True)
    sym_cols = dummies.columns.tolist()

    scaler = StandardScaler()
    X_num = scaler.fit_transform(train[feature_cols_numeric].values)
    X = np.hstack([X_num, dummies.values]) if len(sym_cols) else X_num
    y = train["avg_close_price"].values

    model = LinearRegression()
    model.fit(X, y)

    # 5) Build future rows (LOCF indices)
    companies = pd.read_sql("SELECT symbol, company_name, sector FROM companies ORDER BY symbol;", ENGINE)
    last_idx = (panel.sort_values(["symbol","year"])
                     .groupby("symbol")
                     .tail(1)[["symbol","year"] + feat_cols]
                     .set_index("symbol"))

    future_years = [2025, 2026, 2027]
    rows = []
    for _, c in companies.iterrows():
        sym = c["symbol"]
        if sym not in last_idx.index:
            continue
        last_vals = last_idx.loc[sym].to_dict()
        for yr in future_years:
            row = {"symbol": sym, "year": yr}
            for k,v in last_vals.items(): row[k] = v
            rows.append(row)
    future = pd.DataFrame(rows).dropna(subset=feat_cols)
    if future.empty:
        print("[WARN] No future rows constructed. Falling back to per-company Year→Price regression.")
        return _fallback_year_only(panel)

    # design for future
    future_dummies = pd.get_dummies(future["symbol"], prefix="sym", drop_first=True)
    for mc in set(sym_cols) - set(future_dummies.columns): future_dummies[mc] = 0
    future_dummies = future_dummies[sym_cols] if len(sym_cols) else future_dummies.iloc[:,0:0]

    Xf_num = scaler.transform(future[feature_cols_numeric].values)
    Xf = np.hstack([Xf_num, future_dummies.values]) if len(sym_cols) else Xf_num

    future["predicted_price"] = model.predict(Xf)

    # 6) Last actual
    last_actual = (panel.dropna(subset=["avg_close_price"])
                        .sort_values(["symbol","year"])
                        .groupby("symbol")
                        .tail(1)[["symbol","year","avg_close_price"]]
                        .rename(columns={"year":"last_year","avg_close_price":"last_price"}))

    # wide predictions
    p2025 = future[future["year"]==2025][["symbol","predicted_price"]].rename(columns={"predicted_price":"pred_2025"})
    p2026 = future[future["year"]==2026][["symbol","predicted_price"]].rename(columns={"predicted_price":"pred_2026"})
    p2027 = future[future["year"]==2027][["symbol","predicted_price"]].rename(columns={"predicted_price":"pred_2027"})
    preds = p2025.merge(p2026, on="symbol", how="outer").merge(p2027, on="symbol", how="outer")

    out = (companies.merge(last_actual, on="symbol", how="inner")
                    .merge(preds, on="symbol", how="inner"))
    out = out[out["last_price"] > 0].copy()
    out["roi_3yr"] = (out["pred_2027"] - out["last_price"]) / out["last_price"] * 100.0

    for c in ["last_price","pred_2025","pred_2026","pred_2027","roi_3yr"]:
        out[c] = out[c].round(4)

    # persist
    DDL = """
    CREATE TABLE IF NOT EXISTS predicted_roi (
        symbol TEXT PRIMARY KEY,
        company_name TEXT NOT NULL,
        sector TEXT NOT NULL,
        last_year INT NOT NULL,
        last_price NUMERIC(18,6) NOT NULL,
        pred_2025 NUMERIC(18,6),
        pred_2026 NUMERIC(18,6),
        pred_2027 NUMERIC(18,6),
        roi_3yr NUMERIC(12,6),
        updated_at TIMESTAMP DEFAULT NOW()
    );
    """
    with ENGINE.begin() as conn:
        conn.execute(text(DDL))
        for _, r in out.iterrows():
            conn.execute(
                text("""
                INSERT INTO predicted_roi
                  (symbol, company_name, sector, last_year, last_price,
                   pred_2025, pred_2026, pred_2027, roi_3yr, updated_at)
                VALUES
                  (:symbol, :company_name, :sector, :last_year, :last_price,
                   :pred_2025, :pred_2026, :pred_2027, :roi_3yr, NOW())
                ON CONFLICT (symbol) DO UPDATE SET
                  company_name = EXCLUDED.company_name,
                  sector       = EXCLUDED.sector,
                  last_year    = EXCLUDED.last_year,
                  last_price   = EXCLUDED.last_price,
                  pred_2025    = EXCLUDED.pred_2025,
                  pred_2026    = EXCLUDED.pred_2026,
                  pred_2027    = EXCLUDED.pred_2027,
                  roi_3yr      = EXCLUDED.roi_3yr,
                  updated_at   = NOW();
                """),
                {
                    "symbol": r["symbol"],
                    "company_name": r["company_name"],
                    "sector": r["sector"],
                    "last_year": int(r["last_year"]),
                    "last_price": float(r["last_price"]),
                    "pred_2025": float(r["pred_2025"]),
                    "pred_2026": float(r["pred_2026"]),
                    "pred_2027": float(r["pred_2027"]),
                    "roi_3yr": float(r["roi_3yr"]),
                }
            )

    # show which features push price up/down
    from pandas import Series
    coefs = Series(model.coef_[:len(feature_cols_numeric)], index=feature_cols_numeric)
    print("\n[INFO] Coefficient signs (positive → pushes price up):")
    print(coefs.sort_values())
    return out, coefs

# What I add and might be deleted -------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def _fallback_year_only(panel: pd.DataFrame):
    """Linear regression per company using Year→avg_close_price (no indices),
       to ensure you still get predictions and can proceed."""
    from sklearn.linear_model import LinearRegression
    companies = pd.read_sql("SELECT symbol, company_name, sector FROM companies ORDER BY symbol;", ENGINE)
    out_rows = []
    for sym, g in panel.dropna(subset=["avg_close_price"]).groupby("symbol"):
        if g["year"].nunique() < 3: 
            continue
        X = g[["year"]].values
        y = g["avg_close_price"].values
        model = LinearRegression().fit(X, y)
        last = g.sort_values("year").iloc[-1]
        pred_2025 = float(model.predict([[2025]])[0])
        pred_2026 = float(model.predict([[2026]])[0])
        pred_2027 = float(model.predict([[2027]])[0])
        row = {
            "symbol": sym,
            "last_year": int(last["year"]),
            "last_price": float(last["avg_close_price"]),
            "pred_2025": pred_2025,
            "pred_2026": pred_2026,
            "pred_2027": pred_2027,
        }
        out_rows.append(row)

    out = pd.DataFrame(out_rows)
    if out.empty:
        raise SystemExit("Fallback also failed: need ≥3 years of prices per company.")

    comps = pd.read_sql("SELECT symbol, company_name, sector FROM companies", ENGINE)
    out = comps.merge(out, on="symbol")
    out["roi_3yr"] = (out["pred_2027"] - out["last_price"]) / out["last_price"] * 100.0
    for c in ["last_price","pred_2025","pred_2026","pred_2027","roi_3yr"]:
        out[c] = out[c].round(4)

    with ENGINE.begin() as conn:
        for _, r in out.iterrows():
            conn.execute(
                text("""
                INSERT INTO predicted_roi
                  (symbol, company_name, sector, last_year, last_price,
                   pred_2025, pred_2026, pred_2027, roi_3yr, updated_at)
                VALUES
                  (:symbol, :company_name, :sector, :last_year, :last_price,
                   :pred_2025, :pred_2026, :pred_2027, :roi_3yr, NOW())
                ON CONFLICT (symbol) DO UPDATE SET
                  company_name = EXCLUDED.company_name,
                  sector       = EXCLUDED.sector,
                  last_year    = EXCLUDED.last_year,
                  last_price   = EXCLUDED.last_price,
                  pred_2025    = EXCLUDED.pred_2025,
                  pred_2026    = EXCLUDED.pred_2026,
                  pred_2027    = EXCLUDED.pred_2027,
                  roi_3yr      = EXCLUDED.roi_3yr,
                  updated_at   = NOW();
                """),
                {k:(float(v) if k not in ["symbol","company_name","sector","last_year"] else v) for k,v in {
                    "symbol": r["symbol"],
                    "company_name": r["company_name"],
                    "sector": r["sector"],
                    "last_year": int(r["last_year"]),
                    "last_price": r["last_price"],
                    "pred_2025": r["pred_2025"],
                    "pred_2026": r["pred_2026"],
                    "pred_2027": r["pred_2027"],
                    "roi_3yr": r["roi_3yr"],
                }.items()}
            )
    print("[INFO] Used fallback Year→Price regression. Predictions saved.")
    return out, None

# ----------------------------
# Queries for backend
# ----------------------------
def get_top_by_roi(sectors=None, top_n=5):
    base = "SELECT * FROM predicted_roi"
    if sectors:
        placeholders = ", ".join([f":s{i}" for i,_ in enumerate(sectors)])
        sql = f"{base} WHERE sector IN ({placeholders}) ORDER BY roi_3yr DESC LIMIT :limit"
        params = {f"s{i}": s for i,s in enumerate(sectors)}
    else:
        sql = f"{base} ORDER BY roi_3yr DESC LIMIT :limit"
        params = {}
    params["limit"] = int(top_n)
    return pd.read_sql(text(sql), ENGINE, params=params)

def plan_investment(sectors, amount, top_n=5):
    """
    Equal-weight allocation across Top-N picks in selected sectors.
    """
    picks = get_top_by_roi(sectors, top_n)
    if picks.empty:
        return {"picks": [], "total_invested": 0.0, "expected_value_3y": 0.0, "expected_roi_3y_pct": 0.0}

    capital_each = float(amount) / len(picks)
    rows, expected_total = [], 0.0
    for _, r in picks.iterrows():
        last_price = float(r["last_price"])
        pred_2027  = float(r["pred_2027"])
        units = capital_each / last_price  # fractional shares for simplicity
        value_3y = units * pred_2027
        expected_total += value_3y
        rows.append({
            "symbol": r["symbol"],
            "company_name": r["company_name"],
            "sector": r["sector"],
            "last_price": round(last_price, 4),
            "pred_2027": round(pred_2027, 4),
            "units_bought": round(units, 6),
            "allocated_capital": round(capital_each, 2),
            "expected_value_3y": round(value_3y, 2),
            "roi_3y_pct_single": round((pred_2027 - last_price)/last_price*100.0, 2),
        })

    total_invested = float(amount)
    expected_roi_pct = (expected_total - total_invested) / total_invested * 100.0

    return {
        "picks": rows,
        "total_invested": round(total_invested, 2),
        "expected_value_3y": round(expected_total, 2),
        "expected_roi_3y_pct": round(expected_roi_pct, 2)
    }

# ----------------------------
# Example manual run
# ----------------------------
if __name__ == "__main__":
    _out, _coefs = train_and_store_predictions()
    # Example: sectors chosen by user + amount
    sectors = ["Telecommunication Services", "Energy"]  # user selection
    amount = 15000
    print(get_top_by_roi(sectors, 5)[["company_name","sector","roi_3yr","last_price","pred_2027"]])
    print(plan_investment(sectors, amount, 5))
