import pandas as pd
import streamlit as st

# ---------------------------------------------------------
# 1) LOAD PREDICTIONS
# ---------------------------------------------------------
@st.cache_data
def load_predictions(csv_path="predicted_prices_rf.csv"):
    df = pd.read_csv(csv_path)
    # Ensure correct types
    df["year"] = df["year"].astype(int)
    return df

pred_df = load_predictions()

# ---------------------------------------------------------
# 2) SIDEBAR CONTROLS
# ---------------------------------------------------------
st.sidebar.title("Prediction Settings")

# Year selector (2025–2027)
available_years = sorted(pred_df["year"].unique())
selected_year = st.sidebar.selectbox("Select year", available_years, index=len(available_years)-1)

# Sector filter
all_sectors = sorted(pred_df["sector"].dropna().unique())
sector_filter = st.sidebar.multiselect(
    "Filter by sector (optional)",
    options=all_sectors,
    default=[]
)

# Number of recommendations
top_n = st.sidebar.slider("Number of recommendations", min_value=3, max_value=20, value=5)

# ---------------------------------------------------------
# 3) MAIN UI
# ---------------------------------------------------------
st.title("TASI Stock Price Predictions & Recommendations")
st.write(
    "This app uses a **Random Forest Regressor** trained on financial indicators "
    "to predict future annual stock prices and recommend top companies."
)

st.markdown(f"### Recommendations for **{selected_year}**")

# Button to trigger recommendation
if st.button("Get Recommendations"):
    # Filter by selected year
    df_year = pred_df[pred_df["year"] == selected_year].copy()

    # Apply sector filter if any selected
    if sector_filter:
        df_year = df_year[df_year["sector"].isin(sector_filter)]

    # Sort by predicted price (descending)
    df_year = df_year.sort_values("predicted_price_rf", ascending=False)

    # Take top N
    top_df = df_year.head(top_n).reset_index(drop=True)

    if top_df.empty:
        st.warning("No data available for the selected filters.")
    else:
        st.success(f"Top {len(top_df)} recommended companies for {selected_year}:")
        # Show table
        st.dataframe(
            top_df[[
                "base_symbol",
                "company_name",
                "sector",
                "year",
                "predicted_price_rf"
            ]].rename(columns={
                "base_symbol": "Symbol",
                "company_name": "Company Name",
                "sector": "Sector",
                "year": "Year",
                "predicted_price_rf": "Predicted Price (SAR)"
            })
        )

        # Simple note for explanation
        st.caption(
            "Predictions are based on the latest available financial indicators for each company "
            "and the patterns learned from historical data (2014–2024)."
        )
else:
    st.info("Click **Get Recommendations** to see the top companies for the selected year.")
