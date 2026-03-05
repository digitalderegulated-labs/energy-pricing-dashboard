import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(layout="wide")

st.title("⚡ U.S. Energy Market Dashboard")

API_KEY = st.secrets["EIA_API_KEY"]

url = f"https://api.eia.gov/v2/electricity/rto/region-data/data/?api_key={API_KEY}&frequency=hourly&data[0]=value&start=2024-01-01"

response = requests.get(url)

data = response.json()["response"]["data"]

df = pd.DataFrame(data)

df["period"] = pd.to_datetime(df["period"])

st.subheader("Wholesale Electricity Prices")

fig = px.line(
    df,
    x="period",
    y="value",
    color="region",
    title="Wholesale Electricity Prices by Region"
)

st.plotly_chart(fig, use_container_width=True)

st.dataframe(df)
