import streamlit as st
import pandas as pd
import requests
import plotly.express as px

st.set_page_config(
    page_title="Energy Market Pricing",
    layout="wide"
)

st.title("⚡ Energy Market Pricing Dashboard")

st.markdown("Live PJM electricity pricing data")

# PJM API
url = "https://api.pjm.com/api/v1/da_hrl_lmps"

params = {
    "rowCount": 24,
    "sort": "datetime_beginning_ept",
    "order": "desc"
}

try:
    response = requests.get(url, params=params)
    data = response.json()

    records = data["items"]

    df = pd.DataFrame(records)

    df["datetime_beginning_ept"] = pd.to_datetime(df["datetime_beginning_ept"])

    df = df.sort_values("datetime_beginning_ept")

    st.subheader("Day Ahead LMP Prices")

    fig = px.line(
        df,
        x="datetime_beginning_ept",
        y="total_lmp_da",
        title="PJM Day Ahead Price ($/MWh)",
        markers=True
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Market Price Table")

    st.dataframe(
        df[[
            "datetime_beginning_ept",
            "pnode_name",
            "total_lmp_da"
        ]]
    )

except:
    st.error("Could not load PJM data.")
