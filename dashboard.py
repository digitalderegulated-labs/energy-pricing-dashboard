import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(layout="wide")

st.title("⚡ U.S. Energy Market Dashboard")

# API key from Streamlit secrets
API_KEY = st.secrets["EIA_API_KEY"]

# EIA API request
url = f"https://api.eia.gov/v2/electricity/rto/region-data/data/?api_key={API_KEY}&frequency=hourly&data[0]=value&facets[respondent][]=PJM&start=2024-01-01"

response = requests.get(url)
json_data = response.json()
data = json_data["response"]["data"]

if len(data) == 0:
    st.error("No data returned from EIA API")
    st.stop()

df = pd.DataFrame(data)

# Convert time
df["period"] = pd.to_datetime(df["period"])

# -------------------------------
# MARKET SUMMARY METRICS
# -------------------------------

latest_price = df["value"].iloc[-1]
avg_price = df["value"].mean()
max_price = df["value"].max()

col1, col2, col3 = st.columns(3)

col1.metric("Latest PJM Price", f"${latest_price:,.2f}")
col2.metric("Average Price", f"${avg_price:,.2f}")
col3.metric("Peak Price", f"${max_price:,.2f}")

st.divider()

# -------------------------------
# DAILY PRICE TREND
# -------------------------------

st.subheader("Daily Average Power Price")

daily = df.copy()
daily["date"] = daily["period"].dt.date

daily_avg = daily.groupby("date")["value"].mean().reset_index()

fig1 = px.line(
    daily_avg,
    x="date",
    y="value",
    title="Daily Average Price"
)

st.plotly_chart(fig1, use_container_width=True)

st.divider()

# -------------------------------
# HOURLY HEATMAP
# -------------------------------

st.subheader("Hourly Price Heatmap")

df["hour"] = df["period"].dt.hour
df["day"] = df["period"].dt.date

pivot = df.pivot_table(
    values="value",
    index="hour",
    columns="day",
    aggfunc="mean"
)

fig2 = px.imshow(
    pivot,
    aspect="auto",
    title="Hourly Price Patterns"
)

st.plotly_chart(fig2, use_container_width=True)

st.divider()

# -------------------------------
# RAW DATA
# -------------------------------

st.subheader("Market Data")

st.dataframe(df)
