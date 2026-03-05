import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime

# =========================
# PAGE + BRAND STYLING
# =========================
st.set_page_config(page_title="U.S. Power Market Dashboard", layout="wide")

# --- Brand controls (edit these) ---
COMPANY_NAME = "Digital Deregulated Labs"
TAGLINE = "Energy market intelligence — clean, fast, decision-ready."
FOOTER_NOTE = f"© {datetime.now().year} {COMPANY_NAME}. Internal use."

st.markdown(
    """
<style>
/* App background + typography */
.block-container { padding-top: 1.2rem; padding-bottom: 2.2rem; max-width: 1400px; }
h1, h2, h3 { letter-spacing: -0.02em; }
.small-muted { color: rgba(49, 51, 63, 0.7); font-size: 0.95rem; }
.card {
  border: 1px solid rgba(49, 51, 63, 0.12);
  border-radius: 14px;
  padding: 14px 16px;
  background: rgba(255,255,255,0.85);
  box-shadow: 0 6px 18px rgba(0,0,0,0.05);
}
.card-title { font-size: 0.9rem; color: rgba(49, 51, 63, 0.7); margin-bottom: 6px; }
.card-value { font-size: 1.6rem; font-weight: 700; }
.card-sub { font-size: 0.85rem; color: rgba(49, 51, 63, 0.65); margin-top: 6px; }
.section-title { margin-top: 0.25rem; margin-bottom: 0.25rem; }
hr { margin: 0.8rem 0 1.1rem 0; border-top: 1px solid rgba(49, 51, 63, 0.12); }
.insight {
  border-left: 4px solid rgba(49, 51, 63, 0.28);
  padding: 10px 12px;
  margin-top: 10px;
  border-radius: 10px;
  background: rgba(49, 51, 63, 0.04);
  color: rgba(49, 51, 63, 0.85);
  font-size: 0.95rem;
}
.brandbar {
  display:flex; align-items:flex-start; justify-content:space-between;
  gap: 16px; margin-bottom: 10px;
}
.brand-left { display:flex; flex-direction:column; gap: 4px; }
.brand-name { font-size: 0.95rem; font-weight: 700; letter-spacing: 0.03em; text-transform: uppercase; color: rgba(49, 51, 63, 0.85); }
.brand-title { font-size: 2.1rem; font-weight: 800; letter-spacing: -0.03em; margin-top: 2px; }
.brand-tagline { font-size: 1rem; color: rgba(49, 51, 63, 0.7); }
.brand-right { text-align:right; }
.pill {
  display:inline-block; padding: 6px 10px; border-radius: 999px;
  background: rgba(49, 51, 63, 0.06);
  border: 1px solid rgba(49, 51, 63, 0.10);
  font-size: 0.85rem; color: rgba(49, 51, 63, 0.75);
}
.footer { margin-top: 18px; font-size: 0.85rem; color: rgba(49, 51, 63, 0.6); }
</style>
""",
    unsafe_allow_html=True,
)

# =========================
# HEADER / BRAND
# =========================
st.markdown(
    f"""
<div class="brandbar">
  <div class="brand-left">
    <div class="brand-name">{COMPANY_NAME}</div>
    <div class="brand-title">U.S. Power Market Dashboard</div>
    <div class="brand-tagline">{TAGLINE}</div>
  </div>
  <div class="brand-right">
    <div class="pill">Data: EIA Open Data (Retail electricity prices)</div><br/>
    <div class="pill">Updated on refresh • Cloud deployed</div>
  </div>
</div>
<hr/>
""",
    unsafe_allow_html=True,
)

# =========================
# DATA ACCESS
# =========================
API_KEY = st.secrets["EIA_API_KEY"]

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_eia_retail_prices(state_ids, start="2019-01"):
    """
    Pull monthly retail electricity prices from EIA API v2 for selected states.
    Returns dataframe with at least: period, stateid, stateDescription, sectorName (if present), price
    """
    all_rows = []
    base = "https://api.eia.gov/v2/electricity/retail-sales/data/"
    # A small rowCount keeps responses fast; we filter by start anyway.
    for sid in state_ids:
        params = {
            "api_key": API_KEY,
            "frequency": "monthly",
            "data[0]": "price",
            "facets[stateid][]": sid,
            "start": start,
            "sort[0][column]": "period",
            "sort[0][direction]": "desc",
            "offset": 0,
            "length": 5000,
        }
        r = requests.get(base, params=params, timeout=30)
        j = r.json()
        rows = j.get("response", {}).get("data", [])
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df

    # Normalize columns we rely on
    if "period" in df.columns:
        df["period"] = pd.to_datetime(df["period"], errors="coerce")
    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")

    # Some responses include labels; keep them if present
    # Expected columns often include: stateid, stateDescription, sectorid, sectorName, price, period, units
    return df.dropna(subset=["period", "price"]).sort_values("period")

def kpi_card(title, value, sub=""):
    st.markdown(
        f"""
<div class="card">
  <div class="card-title">{title}</div>
  <div class="card-value">{value}</div>
  <div class="card-sub">{sub}</div>
</div>
""",
        unsafe_allow_html=True,
    )

# =========================
# SIDEBAR CONTROLS
# =========================
st.sidebar.header("Controls")
st.sidebar.caption("Refine the view — keep it decision-ready.")

# Keep it simple + credible (3 flagship states)
default_states = ["PA", "TX", "CA"]
state_ids = st.sidebar.multiselect(
    "States",
    options=["PA", "TX", "CA", "NY", "IL", "OH", "NJ", "FL", "GA", "NC", "VA", "MA", "MI", "AZ", "CO", "WA"],
    default=default_states,
)

start_year = st.sidebar.selectbox("Start year", options=[2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024], index=2)
start = f"{start_year}-01"

# Pull data
with st.spinner("Loading market data..."):
    df = fetch_eia_retail_prices(state_ids=state_ids, start=start)

if df.empty:
    st.error("No data returned for the selected states/time range. Try expanding the date range or state selection.")
    st.stop()

# Sector filter (if present)
sector_col = "sectorName" if "sectorName" in df.columns else None
if sector_col:
    sectors = sorted([s for s in df[sector_col].dropna().unique().tolist()])
    selected_sectors = st.sidebar.multiselect("Sectors", options=sectors, default=sectors)
    df = df[df[sector_col].isin(selected_sectors)].copy()

# If stateDescription exists, use it; else fall back to stateid
state_label_col = "stateDescription" if "stateDescription" in df.columns else "stateid"
df["state_label"] = df[state_label_col].fillna(df.get("stateid", "STATE"))

# =========================
# KPI ROW
# =========================
latest_period = df["period"].max()
recent = df[df["period"] == latest_period].copy()
avg_price = df["price"].mean()
peak_price = df["price"].max()

# Latest median across selected states for a stable "headline"
latest_median = recent["price"].median() if not recent.empty else df.sort_values("period")["price"].iloc[-1]

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("Latest (Median, cents/kWh)", f"{latest_median:,.2f}", sub=f"As of {latest_period.strftime('%b %Y')}")
with k2:
    kpi_card("Average (Selected Range)", f"{avg_price:,.2f}", sub=f"Since {start_year}")
with k3:
    kpi_card("Peak (Selected Range)", f"{peak_price:,.2f}", sub="Highest observed price")
with k4:
    # Spread across states for the latest month: max - min
    if not recent.empty:
        spread = recent["price"].max() - recent["price"].min()
        kpi_card("Latest State Spread", f"{spread:,.2f}", sub="Max–Min (cents/kWh)")
    else:
        kpi_card("Latest State Spread", "—", sub="Insufficient latest data")

st.markdown("<hr/>", unsafe_allow_html=True)

# =========================
# CHARTS (Enterprise-style sections + insights)
# =========================

# --- 1) Trend chart ---
st.subheader("Price Trend (Monthly)")
trend_df = df.copy()

fig_trend = px.line(
    trend_df,
    x="period",
    y="price",
    color="state_label",
    title="Retail Electricity Price — Trend by State (cents/kWh)",
)

st.plotly_chart(fig_trend, use_container_width=True)

# Insight under chart (plain English)
if not recent.empty:
    top_state = recent.sort_values("price", ascending=False).iloc[0]["state_label"]
    low_state = recent.sort_values("price", ascending=True).iloc[0]["state_label"]
    top_val = recent["price"].max()
    low_val = recent["price"].min()
    insight_1 = (
        f"Latest month shows **{top_state}** highest at **{top_val:,.2f}¢/kWh** and "
        f"**{low_state}** lowest at **{low_val:,.2f}¢/kWh**. "
        "Use this view to quickly spot sustained divergence (structural) vs. temporary spikes (short-lived)."
    )
else:
    insight_1 = "Trend view loaded. If the latest month looks sparse, expand the state list or start year."

st.markdown(f'<div class="insight"><b>Insight:</b> {insight_1}</div>', unsafe_allow_html=True)

st.markdown("<hr/>", unsafe_allow_html=True)

# --- 2) Latest month comparison (bar) ---
st.subheader("Latest Month Comparison")
bar_df = recent.groupby("state_label", as_index=False)["price"].mean().sort_values("price", ascending=False)

fig_bar = px.bar(
    bar_df,
    x="state_label",
    y="price",
    title=f"Latest Month Price Comparison (cents/kWh) — {latest_period.strftime('%b %Y')}",
)

st.plotly_chart(fig_bar, use_container_width=True)

if len(bar_df) >= 2:
    leader = bar_df.iloc[0]
    trailer = bar_df.iloc[-1]
    pct = ((leader["price"] - trailer["price"]) / trailer["price"]) * 100 if trailer["price"] != 0 else None
    pct_txt = f"{pct:,.0f}%" if pct is not None else "—"
    insight_2 = (
        f"Price dispersion is meaningful: **{leader['state_label']}** is about **{pct_txt}** above "
        f"**{trailer['state_label']}** this month. If you’re evaluating market entry or pricing strategy, "
        "this view highlights where customer price pressure is likely highest."
    )
else:
    insight_2 = "Add more states to see comparative dispersion and rank-ordering."

st.markdown(f'<div class="insight"><b>Insight:</b> {insight_2}</div>', unsafe_allow_html=True)

st.markdown("<hr/>", unsafe_allow_html=True)

# --- 3) Volatility / stability view (rolling) ---
st.subheader("Stability Monitor (Rolling 6-Month Volatility)")
vol_df = trend_df.sort_values("period").copy()
# rolling std by state
vol_df["roll_std_6m"] = (
    vol_df.groupby("state_label")["price"]
    .rolling(6, min_periods=3)
    .std()
    .reset_index(level=0, drop=True)
)

fig_vol = px.line(
    vol_df.dropna(subset=["roll_std_6m"]),
    x="period",
    y="roll_std_6m",
    color="state_label",
    title="Rolling 6-Month Standard Deviation (cents/kWh)",
)

st.plotly_chart(fig_vol, use_container_width=True)

# Insight: which state is most volatile recently
recent_vol = vol_df[vol_df["period"] == latest_period].dropna(subset=["roll_std_6m"])
if not recent_vol.empty:
    v_top = recent_vol.sort_values("roll_std_6m", ascending=False).iloc[0]
    insight_3 = (
        f"**{v_top['state_label']}** shows the highest recent volatility (6-month std dev **{v_top['roll_std_6m']:.2f}**). "
        "Higher volatility often signals changing cost inputs, regulatory adjustments, or supply/demand imbalance—"
        "which can impact margin and hedging posture."
    )
else:
    insight_3 = (
        "Volatility needs at least ~6 months of data per state. If it’s empty, expand the start year earlier."
    )

st.markdown(f'<div class="insight"><b>Insight:</b> {insight_3}</div>', unsafe_allow_html=True)

st.markdown("<hr/>", unsafe_allow_html=True)

# --- 4) Data table (auditability) ---
st.subheader("Data (Audit & Export)")
st.caption("This table is here so the dashboard remains audit-friendly and trustworthy — you can verify numbers fast.")

show_cols = [c for c in ["period", "stateid", "stateDescription", "sectorName", "price", "units"] if c in df.columns]
st.dataframe(df[show_cols].sort_values("period", ascending=False), use_container_width=True, height=360)

# Simple download
csv = df[show_cols].sort_values("period").to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", data=csv, file_name="eia_retail_electricity_prices.csv", mime="text/csv")

# Footer
st.markdown(f'<div class="footer">{FOOTER_NOTE}</div>', unsafe_allow_html=True)
