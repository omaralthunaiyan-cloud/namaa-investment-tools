import pandas as pd

# =============================
# مسارات الملفات
# =============================
companies_path = r"C:\\Users\\Admin\\Desktop\\IS499\\Companies\\Companies.csv"
dividends_path = r"C:\\Users\\Admin\\Desktop\\IS499\\Dividends\\Divedend.csv"
dividend_payers_path = r"C:\\Users\\Admin\\Desktop\\IS499\\Dividends\\dividend_payers.csv"

# =============================
# قراءة البيانات
# =============================
companies_df = pd.read_csv(companies_path)
dividends_df = pd.read_csv(dividends_path)
dividend_payers_df = pd.read_csv(dividend_payers_path)

# تحويل DividendTTM إلى رقم
dividend_payers_df["DividendTTM"] = pd.to_numeric(dividend_payers_df["DividendTTM"], errors="coerce").fillna(0)

# =============================
# معالجة بيانات التوزيعات
# =============================
dividends_df["Distribution Date"] = pd.to_datetime(dividends_df["Distribution Date"], errors='coerce')
dividends_df["Year"] = dividends_df["Distribution Date"].dt.year
dividends_df["Month"] = dividends_df["Distribution Date"].dt.month
dividends_2024 = dividends_df[dividends_df["Year"] == 2024]

# =============================
# دمج بيانات الشركات مع التوزيعات
# =============================
company_divs_all = pd.merge(dividends_2024, companies_df, on="Symbol", how="inner")

# حساب الأشهر التي وزعت فيها كل شركة خلال 2024
company_months = (
    company_divs_all.groupby("Symbol")["Month"]
    .apply(lambda x: sorted(set(x)))
    .reset_index()
)

# =============================
# دالة عرض النتائج
# =============================
def print_results(df):
    if df.empty:
        print("\n⚠️ No companies found matching your criteria.")
        return
    print("\nSymbol\t\tCompany\t\t\tSector\t\tMonths")
    print("-" * 80)
    for _, row in df.iterrows():
        print(f"{row['Symbol']:<10}\t{row['CompanyName']:<25}\t{row['Sector']:<20}\t{int(row['Months'])}")

# =============================
# الحلقة الرئيسية
# =============================
while True:
    month_choice = input("\nEnter preferred dividend months (1-12) separated by commas (or type 'exit' to quit): ")
    if month_choice.strip().lower() == "exit":
        break

    selected_months = [int(m.strip()) for m in month_choice.split(",") if m.strip().isdigit()]
    if not selected_months:
        print("⚠️ Invalid months input.")
        continue

    # ==========================================================
    # حالة اختيار شهر واحد فقط
    # ==========================================================
    if len(selected_months) == 1:
        target_month = selected_months[0]
        symbols_only_this_month = company_months[
            company_months["Month"].apply(lambda months_list: set(months_list) == {target_month})
        ]["Symbol"].tolist()

        if not symbols_only_this_month:
            print("\n⚠️ No companies distributed only in this month.")
            continue

        result = company_divs_all[
            company_divs_all["Symbol"].isin(symbols_only_this_month)
        ][["Symbol", "CompanyName", "Sector", "Month"]].drop_duplicates()

        result = pd.merge(result, dividend_payers_df, on="Symbol", how="left")
        result["DividendTTM"] = result["DividendTTM"].fillna(0)
        result = result.rename(columns={"Month": "Months"})
        result = result.sort_values(by="DividendTTM", ascending=False)

        print_results(result[["Symbol", "CompanyName", "Sector", "Months"]])
        continue

    # ==========================================================
    # حالة اختيار أكثر من شهر
    # ==========================================================
    selected_set = set(selected_months)
    exact_match_symbols = company_months[
        company_months["Month"].apply(lambda months_list: set(months_list) == selected_set)
    ]["Symbol"].tolist()

    if exact_match_symbols:
        exact_divs = company_divs_all[
            (company_divs_all["Symbol"].isin(exact_match_symbols)) &
            (company_divs_all["Month"].isin(selected_months))
        ]
        exact_result = exact_divs[["Symbol", "CompanyName", "Sector", "Month"]].drop_duplicates()
        exact_result = pd.merge(exact_result, dividend_payers_df, on="Symbol", how="left")
        exact_result["DividendTTM"] = exact_result["DividendTTM"].fillna(0)
        exact_result["Month"] = pd.Categorical(exact_result["Month"], categories=selected_months, ordered=True)
        exact_result = exact_result.sort_values(by=["Month", "DividendTTM"], ascending=[True, False])
        exact_result = exact_result.rename(columns={"Month": "Months"})
        print_results(exact_result[["Symbol", "CompanyName", "Sector", "Months"]])
        continue

    # ==========================================================
    # خطة الاحتياط: شركة واحدة لكل شهر فقط
    # ==========================================================
    fallback_rows = []
    for m in selected_months:
        symbols_only_m = company_months[
            company_months["Month"].apply(lambda months_list: set(months_list) == {m})
        ]["Symbol"].tolist()
        if not symbols_only_m:
            continue
        details_m = companies_df[
            companies_df["Symbol"].isin(symbols_only_m)
        ][["Symbol", "CompanyName", "Sector"]].drop_duplicates()
        if details_m.empty:
            continue
        details_m = pd.merge(details_m, dividend_payers_df, on="Symbol", how="left")
        details_m["DividendTTM"] = details_m["DividendTTM"].fillna(0)
        best_row = details_m.sort_values(by="DividendTTM", ascending=False).iloc[0]
        fallback_rows.append({
            "Symbol": best_row["Symbol"],
            "CompanyName": best_row["CompanyName"],
            "Sector": best_row["Sector"],
            "Months": m,
            "DividendTTM": best_row["DividendTTM"]
        })
    if not fallback_rows:
        print("\n⚠️ No companies found for fallback logic (single-month companies per selected month).")
        continue
    fallback_df = pd.DataFrame(fallback_rows)
    fallback_df["Months"] = pd.Categorical(fallback_df["Months"], categories=selected_months, ordered=True)
    fallback_df = fallback_df.sort_values(by=["Months", "DividendTTM"], ascending=[True, False])
    print_results(fallback_df[["Symbol", "CompanyName", "Sector", "Months"]])
