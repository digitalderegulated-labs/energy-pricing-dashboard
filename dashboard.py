import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(layout="wide")

st.title("⚡ U.S. Energy Market Dashboard")

# get API key from Streamlit secrets
API_KEY = st.secrets["EIA_API_KEY"]

# API request
url = f"https://api.eia.gov/v2/electricity/rto/region-data/data/?api_key={API_KEY}&frequency=hourly&data[0]=value&facets[respondent][]=PJM&start=2024-01-01"

response = requests.get(url)

json_data = response.json()

data = json_data["response"]["data"]

# check if data exists
if len(data) == 0:
    st.error("No data returned from EIA API")
    st.stop()

df = pd.DataFrame(data)

# convert time column
df["period"] = pd.to_datetime(df["period"])

st.subheader("PJM Wholesale Electricity Prices")

fig = px.line(
    df,
    x="period",
    y="value",
    title="PJM Wholesale Price Trend"
)

st.plotly_chart(fig, use_container_width=True)

st.dataframe(df)
