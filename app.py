import streamlit as st
import pandas as pd
import snowflake.connector

# --------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------
st.set_page_config(
    page_title="Procurement Analytics Platform",
    layout="wide"
)

# --------------------------------------------------
# TITLE
# --------------------------------------------------
st.title("📊 Procurement Analytics Platform")
st.markdown(
    "<div style='color:#9aa0a6;font-size:14px;'>Interactive procurement analytics cockpit for executive decision-making</div>",
    unsafe_allow_html=True
)

# --------------------------------------------------
# SNOWFLAKE CONNECTION
# --------------------------------------------------
@st.cache_resource
def get_connection():
    conn = snowflake.connector.connect(
        user=st.secrets["snowflake"]["user"],
        password=st.secrets["snowflake"]["password"],
        account=st.secrets["snowflake"]["account"],
        warehouse=st.secrets["snowflake"]["warehouse"],
        database=st.secrets["snowflake"]["database"],
        schema=st.secrets["snowflake"]["schema"]
    )
    return conn

conn = get_connection()

# --------------------------------------------------
# LOAD DATA FROM SNOWFLAKE
# --------------------------------------------------
@st.cache_data(ttl=600)
def load_base_data():

    query = """
        SELECT
            transaction_date,
            vendor_name,
            category,
            city,
            quantity,
            unit_price,
            discount_pct,
            invoice_amount
        FROM PROCUREMENT_DB.TRANSFORMED.PROCUREMENT_CLEAN
    """

    df = pd.read_sql(query, conn)
    return df

base_df = load_base_data()

# --------------------------------------------------
# DATA PREPARATION
# --------------------------------------------------
base_df["TRANSACTION_DATE"] = pd.to_datetime(base_df["TRANSACTION_DATE"])
base_df["YEAR"] = base_df["TRANSACTION_DATE"].dt.year
base_df["MONTH"] = base_df["TRANSACTION_DATE"].dt.month_name()

# --------------------------------------------------
# SIDEBAR NAVIGATION
# --------------------------------------------------
st.sidebar.title("Navigation")

page = st.sidebar.radio(
    "Go to",
    [
        "Executive Dashboard",
        "Vendor Analysis",
        "Category Analysis",
        "City Analysis",
        "Discount Analysis",
        "Risk & Operations"
    ]
)

# --------------------------------------------------
# FILTERS
# --------------------------------------------------
st.sidebar.title("Filters")

year_options = ["All"] + sorted(base_df["YEAR"].unique().tolist())
selected_year = st.sidebar.selectbox("Year", year_options)

month_options = ["All"] + sorted(base_df["MONTH"].unique().tolist())
selected_month = st.sidebar.selectbox("Month", month_options)

selected_vendors = st.sidebar.multiselect(
    "Vendor", sorted(base_df["VENDOR_NAME"].unique())
)

selected_categories = st.sidebar.multiselect(
    "Category", sorted(base_df["CATEGORY"].unique())
)

selected_cities = st.sidebar.multiselect(
    "City", sorted(base_df["CITY"].unique())
)

min_spend, max_spend = st.sidebar.slider(
    "Invoice Amount Range",
    int(base_df["INVOICE_AMOUNT"].min()),
    int(base_df["INVOICE_AMOUNT"].max()),
    (
        int(base_df["INVOICE_AMOUNT"].min()),
        int(base_df["INVOICE_AMOUNT"].max())
    )
)

discount_threshold = st.sidebar.slider("Minimum Discount %", 0, 100, 0)

# --------------------------------------------------
# APPLY FILTERS
# --------------------------------------------------
filtered_df = base_df.copy()

if selected_year != "All":
    filtered_df = filtered_df[filtered_df["YEAR"] == selected_year]

if selected_month != "All":
    filtered_df = filtered_df[filtered_df["MONTH"] == selected_month]

if selected_vendors:
    filtered_df = filtered_df[filtered_df["VENDOR_NAME"].isin(selected_vendors)]

if selected_categories:
    filtered_df = filtered_df[filtered_df["CATEGORY"].isin(selected_categories)]

if selected_cities:
    filtered_df = filtered_df[filtered_df["CITY"].isin(selected_cities)]

filtered_df = filtered_df[
    (filtered_df["INVOICE_AMOUNT"] >= min_spend) &
    (filtered_df["INVOICE_AMOUNT"] <= max_spend) &
    (filtered_df["DISCOUNT_PCT"] >= discount_threshold)
]

if filtered_df.empty:
    st.warning("No data available for selected filters")
    st.stop()

# --------------------------------------------------
# KPI CALCULATIONS
# --------------------------------------------------
total_spend = filtered_df["INVOICE_AMOUNT"].sum()
total_quantity = filtered_df["QUANTITY"].sum()
vendor_count = filtered_df["VENDOR_NAME"].nunique()
category_count = filtered_df["CATEGORY"].nunique()
city_count = filtered_df["CITY"].nunique()

# --------------------------------------------------
# EXECUTIVE DASHBOARD
# --------------------------------------------------
if page == "Executive Dashboard":

    st.subheader("Executive Overview")

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Total Spend", f"{total_spend:,.0f}")
    c2.metric("Total Quantity", f"{total_quantity:,.0f}")
    c3.metric("Vendors", vendor_count)
    c4.metric("Categories", category_count)
    c5.metric("Cities", city_count)

    st.divider()

    st.subheader("Monthly Spend Trend")

    trend_df = (
        filtered_df
        .groupby(pd.Grouper(key="TRANSACTION_DATE", freq="M"))
        .agg(total_spend=("INVOICE_AMOUNT", "sum"))
    )

    st.line_chart(trend_df)

# --------------------------------------------------
# VENDOR ANALYSIS
# --------------------------------------------------
elif page == "Vendor Analysis":

    st.subheader("Top Vendors by Spend")

    vendor_spend = (
        filtered_df.groupby("VENDOR_NAME")["INVOICE_AMOUNT"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
    )

    st.bar_chart(vendor_spend)

    st.subheader("Vendor Negotiation Targets")

    vendor_targets = (
        filtered_df.groupby("VENDOR_NAME")
        .agg(
            total_spend=("INVOICE_AMOUNT", "sum"),
            avg_discount=("DISCOUNT_PCT", "mean")
        )
        .sort_values("total_spend", ascending=False)
    )

    st.dataframe(vendor_targets)

# --------------------------------------------------
# CATEGORY ANALYSIS
# --------------------------------------------------
elif page == "Category Analysis":

    st.subheader("Spend by Category")

    category_spend = (
        filtered_df.groupby("CATEGORY")["INVOICE_AMOUNT"]
        .sum()
        .sort_values(ascending=False)
    )

    st.bar_chart(category_spend)

# --------------------------------------------------
# CITY ANALYSIS
# --------------------------------------------------
elif page == "City Analysis":

    st.subheader("City-wise Spend")

    city_spend = (
        filtered_df.groupby("CITY")["INVOICE_AMOUNT"]
        .sum()
        .sort_values(ascending=False)
    )

    st.bar_chart(city_spend)

# --------------------------------------------------
# DISCOUNT ANALYSIS
# --------------------------------------------------
elif page == "Discount Analysis":

    st.subheader("Discount Effectiveness")

    discount_vendor = (
        filtered_df.groupby("VENDOR_NAME")
        .agg(
            avg_discount=("DISCOUNT_PCT", "mean"),
            total_spend=("INVOICE_AMOUNT", "sum")
        )
        .sort_values("avg_discount", ascending=False)
    )

    st.dataframe(discount_vendor)

# --------------------------------------------------
# RISK & OPERATIONS
# --------------------------------------------------
elif page == "Risk & Operations":

    st.subheader("Spend Concentration Risk")

    pareto = (
        filtered_df.groupby("VENDOR_NAME")["INVOICE_AMOUNT"]
        .sum()
        .sort_values(ascending=False)
    )

    st.line_chart(pareto.cumsum() / pareto.sum())

    st.subheader("Filtered Procurement Records")

    st.dataframe(filtered_df)