import streamlit as st
import pandas as pd
import requests

st.title("Energy API Debug")

API_KEY = st.secrets["EIA_API_KEY"]

url = f"https://api.eia.gov/v2/electricity/rto/region-data/data/?api_key={API_KEY}&frequency=hourly&data[0]=value"

response = requests.get(url)

data = response.json()

st.write("RAW API RESPONSE")
st.write(data)

df = pd.DataFrame(data["response"]["data"])

st.write("DATAFRAME")
st.write(df)
