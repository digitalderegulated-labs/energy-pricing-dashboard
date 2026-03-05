import streamlit as st
import requests
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")

st.title("⚡ U.S. Power Market Dashboard")

API_KEY = st.secrets["EIA_API_KEY"]


def get_eia_data(url):
    r = requests.get(url)
    data = r.json()

    df = pd.DataFrame(data["response"]["data"])

    df["period"] = pd.to_datetime(df["period"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    return df


# PJM price
pjm_url = f"https://api.eia.gov/v2/electricity/retail-sales/data/?api_key={API_KEY}&frequency=monthly&data[0]=price&facets[stateid][]=PA"

pjm = get_eia_data(pjm_url)


# Texas price
texas_url = f"https://api.eia.gov/v2/electricity/retail-sales/data/?api_key={API_KEY}&frequency=monthly&data[0]=price&facets[stateid][]=TX"

texas = get_eia_data(texas_url)


# California price
ca_url = f"https://api.eia.gov/v2/electricity/retail-sales/data/?api_key={API_KEY}&frequency=monthly&data[0]=price&facets[stateid][]=CA"

california = get_eia_data(ca_url)


# ---- Metrics ----

col1, col2, col3 = st.columns(3)

col1.metric(
    "Pennsylvania Power Price",
    f"{pjm['value'].iloc[0]:.2f} cents/kWh"
)

col2.metric(
    "Texas Power Price",
    f"{texas['value'].iloc[0]:.2f} cents/kWh"
)

col3.metric(
    "California Power Price",
    f"{california['value'].iloc[0]:.2f} cents/kWh"
)

st.divider()

# Combine markets

df_all = pd.concat([
    pjm.assign(market="Pennsylvania"),
    texas.assign(market="Texas"),
    california.assign(market="California")
])


fig = px.line(
    df_all,
    x="period",
    y="value",
    color="market",
    title="Retail Electricity Price Trends"
)

st.plotly_chart(fig, use_container_width=True)
