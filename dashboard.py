import streamlit as st
import requests
import pandas as pd
import plotly.express as px

st.set_page_config(layout="wide")

st.title("⚡ U.S. Power Market Dashboard")

API_KEY = st.secrets["EIA_API_KEY"]

def get_data(series_id):
    url = f"https://api.eia.gov/v2/seriesid/{series_id}?api_key={API_KEY}"
    r = requests.get(url)
    data = r.json()

    df = pd.DataFrame(data["response"]["data"])

    df["period"] = pd.to_datetime(df["period"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")

    return df


# PJM wholesale electricity price
pjm = get_data("ELEC.PRICE.PJM-ALL.M")

# ERCOT price
ercot = get_data("ELEC.PRICE.ERCOT-ALL.M")

# California price
caiso = get_data("ELEC.PRICE.CAISO-ALL.M")

# Natural gas price
gas = get_data("NG.RNGWHHD.M")

# Electricity demand
demand = get_data("EBA.US48-ALL.D.H")

# ---- metrics ----

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "PJM Power Price",
    f"${pjm['value'].iloc[0]:.2f}/MWh"
)

col2.metric(
    "ERCOT Power Price",
    f"${ercot['value'].iloc[0]:.2f}/MWh"
)

col3.metric(
    "CAISO Power Price",
    f"${caiso['value'].iloc[0]:.2f}/MWh"
)

col4.metric(
    "Henry Hub Gas",
    f"${gas['value'].iloc[0]:.2f}/MMBtu"
)

st.divider()

# ---- power price chart ----

power_df = pd.concat([
    pjm.assign(market="PJM"),
    ercot.assign(market="ERCOT"),
    caiso.assign(market="CAISO")
])

fig = px.line(
    power_df,
    x="period",
    y="value",
    color="market",
    title="Wholesale Power Prices"
)

st.plotly_chart(fig, use_container_width=True)

# ---- demand chart ----

fig2 = px.line(
    demand,
    x="period",
    y="value",
    title="U.S. Electricity Demand"
)

st.plotly_chart(fig2, use_container_width=True)
