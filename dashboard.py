import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(layout="wide")

st.title("⚡ U.S. Energy Market Dashboard")

API_KEY = st.secrets["EIA_API_KEY"]

# Use working EIA dataset (wholesale electricity prices)
url = f"https://api.eia.gov/v2/electricity/retail-sales/data/?api_key={API_KEY}&frequency=monthly&data[0]=price"

response = requests.get(url)

data = response.json()["response"]["data"]

df = pd.DataFrame(data)

# convert date
df["period"] = pd.to_datetime(df["period"])

# ----------------------------------
# METRICS
# ----------------------------------

latest_price = df["price"].iloc[-1]
avg_price = df["price"].mean()
max_price = df["price"].max()

col1, col2, col3 = st.columns(3)

col1.metric("Latest Electricity Price", f"${latest_price:,.2f}")
col2.metric("Average Price", f"${avg_price:,.2f}")
col3.metric("Peak Price", f"${max_price:,.2f}")

st.divider()

# ----------------------------------
# PRICE TREND
# ----------------------------------

fig = px.line(
    df,
    x="period",
    y="price",
    color="stateDescription",
    title="Electricity Price Trend"
)

st.plotly_chart(fig, use_container_width=True)

st.divider()

st.subheader("Raw Data")

st.dataframe(df)
