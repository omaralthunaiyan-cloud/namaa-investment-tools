import pandas as pd

# ===========================
# File Paths
# ===========================
COMPANIES_FILE = r"C:\Users\Admin\Desktop\companies.csv"
INDICES_FILE = r"C:\Users\Admin\Desktop\indices_cleaned.csv"


# ===========================
# Load Data
# ===========================
companies_df = pd.read_csv(COMPANIES_FILE)
indices_df = pd.read_csv(INDICES_FILE)

# Remove ".SR" from symbols
indices_df["symbol"] = indices_df["symbol"].str.replace(".SR", "", regex=False)


# ===========================
# Indicator Mapping
# ===========================
INDICATOR_MAP = {
    "capital": "Capital",
    "total_liabilities": "Total Liabilities",
    "net_income": "Net Income",
    "roe": "Return on Equity",
    "roa": "Return on Assets",
    "eps": "Earnings Per Share",
    "pe": "Price-to-Earnings Ratio",
    "bvps": "Book Value Per Share",
    "de": "Debt-to-Equity Ratio"
}

PERCENTAGE_FIELDS = ["roe", "roa"]
ROUND_2_FIELDS = ["eps", "pe", "bvps", "de"]


# ===========================
# Resolve Input: Name or Symbol
# ===========================
def resolve_company_input(user_input):
    user_input_lower = user_input.strip().lower()

    # 1) Exact symbol match
    symbol_match = companies_df[
        companies_df["symbol"].astype(str).str.lower() == user_input_lower
    ]
    if not symbol_match.empty:
        return symbol_match.iloc[0]["symbol"]

    # 2) Company name match (full or partial)
    name_match = companies_df[
        companies_df["company_name"].str.lower().str.contains(user_input_lower)
    ]
    if not name_match.empty:
        return name_match.iloc[0]["symbol"]

    return None


# ===========================
# Main Function
# ===========================
def get_company_indices(symbol, selected_indicators, selected_years):
    company = companies_df[companies_df["symbol"].astype(str) == str(symbol)]

    if company.empty:
        return {"error": "Company not found."}

    company_name = company.iloc[0]["company_name"]
    sector = company.iloc[0]["sector"]

    df_filtered = indices_df[
        (indices_df["symbol"].astype(str) == str(symbol)) &
        (indices_df["year"].isin(selected_years))
    ]

    if df_filtered.empty:
        return {"error": "No data available for the selected years."}

    output_data = []
    for _, row in df_filtered.iterrows():
        entry = {"Year": int(row["year"])}

        for col in selected_indicators:
            if col in PERCENTAGE_FIELDS:
                entry[INDICATOR_MAP[col]] = f"{round(row[col] * 100, 2)}%"
            elif col in ROUND_2_FIELDS:
                entry[INDICATOR_MAP[col]] = round(row[col], 2)
            else:
                entry[INDICATOR_MAP[col]] = row[col]

        output_data.append(entry)

    return {
        "Symbol": symbol,
        "CompanyName": company_name,
        "Sector": sector,
        "Indicators": [INDICATOR_MAP[i] for i in selected_indicators],
        "Years": selected_years,
        "Data": output_data
    }


# ===========================
# Interactive Input
# ===========================
if __name__ == "__main__":

    print("\n========== Get Indices for a Company ==========\n")

    # 1) User Input (Symbol or Name)
    user_input = input("Enter the company symbol or company name: ").strip()

    resolved_symbol = resolve_company_input(user_input)

    if resolved_symbol is None:
        print("\nError: Company not found. Please check the input.")
        exit()

    symbol = str(resolved_symbol)

    # 2) Show Indicators
    print("\nAvailable Indicators:")
    for key, value in INDICATOR_MAP.items():
        print(f"- {key}  -->  {value}")

    print("\nEnter the indicators you want separated by commas.")
    print("Example: roe, eps, pe, capital")
    indicators_input = input("\nIndicators: ").replace(" ", "").lower()
    selected_indicators = indicators_input.split(",")

    selected_indicators = [i for i in selected_indicators if i in INDICATOR_MAP]

    if not selected_indicators:
        print("\nError: No valid indicators were entered.")
        exit()

    # 3) Year Selection — Free Choice 2014–2024
    print("\nSelect the years you want (allowed: 2014–2024).")
    print("Enter years separated by commas.")
    print("Example: 2019, 2021, 2023")
    print("Or enter: all")

    years_input = input("\nYears: ").replace(" ", "").lower()

    if years_input == "all":
        selected_years = list(range(2014, 2025))
    else:
        try:
            selected_years = [int(y) for y in years_input.split(",")]
        except:
            print("Invalid year format.")
            exit()

        # Validate year range
        for y in selected_years:
            if y < 2014 or y > 2024:
                print(f"Invalid year detected: {y}. Allowed range is 2014–2024.")
                exit()

    # 4) Execute
    result = get_company_indices(symbol, selected_indicators, selected_years)

    print("\n========== Results ==========\n")

    if "error" in result:
        print(result["error"])
        exit()

    print(f"Symbol: {result['Symbol']}")
    print(f"Company Name: {result['CompanyName']}")
    print(f"Sector: {result['Sector']}")
    print(f"Selected Indicators: {result['Indicators']}")
    print(f"Years Included: {result['Years']}")

    print("\nData:\n")
    for entry in result["Data"]:
        print("--------------")
        print(f"Year: {entry['Year']}")
        for key in entry:
            if key != "Year":
                print(f"{key}: {entry[key]}")
