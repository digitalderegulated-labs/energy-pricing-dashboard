import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime

st.set_page_config(layout="wide")

st.title("⚡ Energy Market Pricing Dashboard")

# get today's date
today = datetime.today().strftime("%Y%m%d")

url = f"http://mis.nyiso.com/public/csv/realtime/{today}realtime_zone.csv"

st.write("Data Source:", url)

try:
    df = pd.read_csv(url)

    df["Time Stamp"] = pd.to_datetime(df["Time Stamp"])

    st.subheader("Real Time Electricity Prices")

    fig = px.line(
        df,
        x="Time Stamp",
        y="LBMP ($/MWHr)",
        color="Name"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Market Data")

    st.dataframe(df)

except:
    st.error("Today's NYISO file is not available yet.")
