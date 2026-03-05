import streamlit as st
import requests
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")

st.title("⚡ U.S. Power Market Dashboard")

API_KEY = st.secrets["EIA_API_KEY"]


# ---------------------------
# DATA FUNCTION
# ---------------------------

def get_eia_data(url):

    r = requests.get(url)
    data = r.json()

    if "response" not in data:
        st.error("EIA API returned unexpected format")
        st.write(data)
        st.stop()

    df = pd.DataFrame(data["response"]["data"])

    # Convert columns safely
    if "period" in df.columns:
        df["period"] = pd.to_datetime(df["period"])

    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")

    return df


# ---------------------------
# API REQUESTS
# ---------------------------

pjm_url = f"https://api.eia.gov/v2/electricity/retail-sales/data/?api_key={API_KEY}&frequency=monthly&data[0]=price&facets[stateid][]=PA"

texas_url = f"https://api.eia.gov/v2/electricity/retail-sales/data/?api_key={API_KEY}&frequency=monthly&data[0]=price&facets[stateid][]=TX"

ca_url = f"https://api.eia.gov/v2/electricity/retail-sales/data/?api_key={API_KEY}&frequency=monthly&data[0]=price&facets[stateid][]=CA"


pjm = get_eia_data(pjm_url)
texas = get_eia_data(texas_url)
california = get_eia_data(ca_url)


# ---------------------------
# METRICS
# ---------------------------

col1, col2, col3 = st.columns(3)

col1.metric(
    "Pennsylvania Electricity Price",
    f"{pjm['price'].iloc[0]:.2f} cents/kWh"
)

col2.metric(
    "Texas Electricity Price",
    f"{texas['price'].iloc[0]:.2f} cents/kWh"
)

col3.metric(
    "California Electricity Price",
    f"{california['price'].iloc[0]:.2f} cents/kWh"
)

st.divider()


# ---------------------------
# COMBINE DATA
# ---------------------------

df_all = pd.concat([
    pjm.assign(market="Pennsylvania"),
    texas.assign(market="Texas"),
    california.assign(market="California")
])


# ---------------------------
# CHART
# ---------------------------

fig = px.line(
    df_all,
    x="period",
    y="price",
    color="market",
    title="Retail Electricity Price Trends"
)

st.plotly_chart(fig, use_container_width=True)
