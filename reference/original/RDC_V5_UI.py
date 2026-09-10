# المكتبات المستخدمة :
import sys
import math
import itertools
import pandas as pd

# File paths :
PATH_COMPANIES = r"C:\Users\Admin\Desktop\IS499\Companies\Companies.csv"
PATH_DIVIDENDS = r"C:\Users\Admin\Desktop\IS499\Dividends\Divedend.csv"
PATH_PAYERS    = r"C:\Users\Admin\Desktop\IS499\Dividends\dividend_payers.csv"
PATH_PRICES    = r"C:\Users\Admin\Desktop\IS499\HistoricalPrices\Historical_For_RDC.csv"

# Sector choices :
SECTOR_CHOICES = {
    1: "Energy", 2: "Materials", 3: "Capital Goods", 4: "Commercial & Professional Svc",
    5: "Transportation", 6: "Consumer Durables & Apparel", 7: "Consumer Services",
    8: "Media and Entertainment", 9: "Consumer Discretionary Distribution & Retail",
    10: "Consumer Staples Distribution & Retail", 11: "Food & Beverages",
    12: "Household & Personal Products", 13: "Health Care Equipment & Svc",
    14: "Pharma, Biotech & Life Science", 15: "Banks", 16: "Financial Services",
    17: "Insurance", 18: "Software & Services", 19: "Telecommunication Services",
    20: "Utilities", 21: "REITs", 22: "Real Estate Mgmt & Dev't"
}

# -------------------------------------------------------------------------
# ------------------------- USER INPUT FUNCTIONS --------------------------
# -------------------------------------------------------------------------

def prompt_amount():
    while True:
        s = input("Q1 - Enter Amount in SAR (must be > 0): ").strip()
        try:
            val = float(s)
            if val > 0:
                return val
            print("Amount must be greater than 0.")
        except:
            print("Please enter a numeric value.")

def prompt_coverage_preference():
    valid = {0, 25, 50, 75, 100}
    while True:
        s = input("Q2 - Enter Coverage Preference % (0,25,50,75,100): ").strip().replace("%", "")
        try:
            v = int(s)
            if v in valid:
                return v
            print("Choose one of 0,25,50,75,100.")
        except:
            print("Please enter an integer.")

def prompt_profit_preference(cov_pref):
    valid = {0, 25, 50, 75, 100}
    while True:
        s = input("Q3 - Enter Profit Preference % (0,25,50,75,100). Must sum to 100 with coverage: ").strip().replace("%", "")
        try:
            v = int(s)
            if v in valid and v + cov_pref == 100:
                return v
            print("Profit % must be one of 0,25,50,75,100 and sum with coverage to 100.")
        except:
            print("Please enter an integer.")

def prompt_sectors():
    print("Q4 - Enter Sector numbers separated by commas (or 0 for all):")
    for num, name in SECTOR_CHOICES.items():
        print(f"{num}. {name}")
    s = input("Your choice: ").strip()
    if not s:
        return []
    parts = [p.strip() for p in s.split(",") if p.strip()]
    nums = []
    for p in parts:
        try:
            nums.append(int(p))
        except:
            pass
    if 0 in nums or len(nums) == 0:
        return []
    return [SECTOR_CHOICES[n] for n in nums if n in SECTOR_CHOICES]

def prompt_company_range():
    while True:
        try:
            min_c = int(input("Q5 - Enter minimum number of companies (e.g. 2): ").strip())
            max_c = int(input("Enter maximum number of companies (e.g. 5): ").strip())
            if 1 <= min_c <= max_c:
                return min_c, max_c
            print("Minimum must be <= maximum and both > 0.")
        except:
            print("Please enter valid integers.")

# -------------------------------------------------------------------------
# -------------------------- DATA LOADING --------------------------------
# -------------------------------------------------------------------------

def read_companies(path):
    df = pd.read_csv(path)
    df["Symbol"] = df["Symbol"].astype(str).str.strip()
    df["CompanyName"] = df["CompanyName"].astype(str).str.strip()
    df["Sector"] = df["Sector"].astype(str).str.strip()
    return df

def read_dividends(path):
    df = pd.read_csv(path)
    df["Symbol"] = df["Symbol"].astype(str).str.strip()
    df["Distribution Date"] = pd.to_datetime(df["Distribution Date"], errors="coerce", infer_datetime_format=True)
    df["Dividend Amount"] = pd.to_numeric(df["Dividend Amount"], errors="coerce")
    return df

def read_payers(path):
    df = pd.read_csv(path)
    df["Symbol"] = df["Symbol"].astype(str).str.strip()
    df["DividendTTM"] = pd.to_numeric(df["DividendTTM"], errors="coerce")
    return df

def read_prices(path):
    df = pd.read_csv(path)
    df["Symbol"] = df["Symbol"].astype(str).str.strip()
    df["Historical_Price"] = pd.to_numeric(df["Historical_Price"], errors="coerce")
    return df

# -------------------------------------------------------------------------
# -------------------------- CORE CALCULATIONS ----------------------------
# -------------------------------------------------------------------------

def compute_yields_on_universe(universe_df: pd.DataFrame, prices_df: pd.DataFrame) -> pd.DataFrame:
    df = universe_df.merge(prices_df, on="Symbol", how="left")
    df["LastClose"] = df["Historical_Price"]
    df["YieldDecimal"] = df.apply(
        lambda r: (float(r["DividendTTM"]) / float(r["LastClose"]))
        if pd.notnull(r["DividendTTM"]) and pd.notnull(r["LastClose"]) and float(r["LastClose"]) > 0
        else 0.0,
        axis=1,
    )
    df["YieldPct"] = df["YieldDecimal"] * 100.0
    return df

def months_covered_2024(dividends_df, symbol):
    sel = dividends_df[
        (dividends_df["Symbol"] == symbol)
        & (dividends_df["Distribution Date"].dt.year == 2024)
    ]
    months = set()
    for _, row in sel.iterrows():
        dt = row["Distribution Date"]
        if pd.notnull(dt):
            months.add(int(dt.month))
    return months

def portfolio_metrics(symbols, base_df, dividends_df, invest_amount_sar, w_cov, w_profit, month_map):
    if not symbols:
        return {"rows": [], "months": [], "avg_profit_pct": 0.0, "ranking": 0.0}
    sub = base_df[base_df["Symbol"].isin(symbols)].copy()
    avg_profit_pct = sub["YieldPct"].mean() if not sub.empty else 0.0
    months_union = set()
    for s in symbols:
        months_union |= month_map.get(s, set())
    coverage_pct = (len(months_union) / 12.0) * 100.0
    ranking = (w_cov * coverage_pct) + (w_profit * avg_profit_pct)
    per_company = round(invest_amount_sar / max(1, len(symbols)), 2)
    name_map = dict(zip(base_df["Symbol"], base_df["CompanyName"]))
    rows = [{"Symbol": s, "Company Name": name_map.get(s, ""), "Amount (SAR)": per_company} for s in symbols]
    return {"rows": rows, "months": sorted(list(months_union)), "avg_profit_pct": round(avg_profit_pct, 2), "ranking": round(ranking, 2)}

def coverage_target_months(cov_pref_pct: int) -> int:
    mapping = {0: 0, 25: 3, 50: 6, 75: 9, 100: 12}
    return mapping.get(cov_pref_pct, 6)

def coverage_closeness_pct(months_count: int, target_months: int) -> float:
    diff = abs(months_count - target_months)
    return max(0.0, 100.0 - (diff / 12.0) * 100.0)

def score_portfolio(symbols, base_df, dividends_df, w_cov, w_profit, target_months, month_map):
    if not symbols:
        return -1e9
    sub = base_df[base_df["Symbol"].isin(symbols)].copy()
    avg_profit_pct = sub["YieldPct"].mean() if not sub.empty else 0.0
    months_union = set()
    for s in symbols:
        months_union |= month_map.get(s, set())
    cov_close = coverage_closeness_pct(len(months_union), target_months)
    return (w_cov * cov_close) + (w_profit * avg_profit_pct)

def generate_candidate_portfolios(base_df, dividends_df, w_cov, w_profit, target_months, min_companies, max_companies, month_map):
    base_df = base_df.copy()
    base_df["CovMonthsCount2024"] = base_df["Symbol"].apply(lambda s: len(month_map.get(s, set())))
    base_df["Heuristic"] = base_df["YieldPct"] + 10.0 * base_df["CovMonthsCount2024"]

    N = min(25, len(base_df))  # تقليل عدد الشركات المرشحة لتسريع الكود
    cand = base_df.sort_values("Heuristic", ascending=False).head(N)
    symbols = list(cand["Symbol"])

    portfolios = []
    for r in range(min_companies, max_companies + 1):
        for combo in itertools.combinations(symbols, r):
            portfolios.append(tuple(sorted(combo)))

    scored = []
    for combo in portfolios:
        s = score_portfolio(combo, base_df, dividends_df, w_cov, w_profit, target_months, month_map)
        scored.append((combo, s))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored

def select_top3_unique(scored_portfolios):
    seen = set()
    top = []
    for combo, _ in scored_portfolios:
        key = frozenset(combo)
        if key in seen:
            continue
        seen.add(key)
        top.append(combo)
        if len(top) == 3:
            break
    return top

# -------------------------------------------------------------------------
# ------------------------------ MAIN -------------------------------------
# -------------------------------------------------------------------------

def main():
    companies = read_companies(PATH_COMPANIES)
    dividends = read_dividends(PATH_DIVIDENDS)
    payers = read_payers(PATH_PAYERS)
    prices = read_prices(PATH_PRICES)

    amount_sar = prompt_amount()
    cov_pref = prompt_coverage_preference()
    prof_pref = prompt_profit_preference(cov_pref)
    sector_filter = prompt_sectors()
    min_companies, max_companies = prompt_company_range()

    universe = companies.merge(payers, on="Symbol", how="inner")
    if sector_filter:
        universe = universe[universe["Sector"].isin(sector_filter)].copy()
    if universe.empty:
        print("\nNo companies match the selected sector filter (and dividend payers).")
        return

    enriched = compute_yields_on_universe(universe, prices)
    base = enriched[["Symbol", "CompanyName", "Sector", "DividendTTM", "LastClose", "YieldDecimal", "YieldPct"]].copy()

    # حساب تغطية الأشهر مرة واحدة فقط (تحسين رئيسي)
    month_map = {s: months_covered_2024(dividends, s) for s in base["Symbol"]}

    w_cov = cov_pref / 100.0
    w_profit = prof_pref / 100.0
    target_m = coverage_target_months(cov_pref)

    scored = generate_candidate_portfolios(base, dividends, w_cov, w_profit, target_m, min_companies, max_companies, month_map)
    top3 = select_top3_unique(scored)

    def print_option(name, combo):
        metrics = portfolio_metrics(combo, base, dividends, amount_sar, w_cov, w_profit, month_map)
        print("=" * 70)
        print(name)
        print("-" * 70)
        if not metrics["rows"]:
            print("No companies in this option.")
            return
        df_rows = pd.DataFrame(metrics["rows"])
        print(df_rows.to_string(index=False))
        print(f"\nMonths covered (2024): {metrics['months']}")
        print(f"Percentage of coverage: {round((len(metrics['months']) / 12) * 100, 2)}%")
        print(f"Average of the profit: {metrics['avg_profit_pct']}%")
        print(f"Score: {metrics['ranking']}")
        print("=" * 70 + "\n")

    for idx, combo in enumerate(top3, start=1):
        print_option(f"Option {idx}", combo)

    print("Your Inputs:")
    print(f"- Amount (SAR): {amount_sar}")
    print(f"- Coverage Preference %: {cov_pref}")
    print(f"- Profit Preference %: {prof_pref}")
    if sector_filter:
        print(f"- Sector Filter: {', '.join(sector_filter)}")
    else:
        print("- Sector Filter: All sectors")
    print(f"- Company Range: {min_companies} to {max_companies}")

if __name__ == "__main__":
    main()
