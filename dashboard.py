import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import zipfile
import io
from datetime import datetime, timedelta, timezone

# =========================
# PAGE + BRAND
# =========================
st.set_page_config(page_title="ISO LMP Dashboard", layout="wide")

COMPANY_NAME = st.secrets.get("COMPANY_NAME", "Digital Deregulated Labs")
TAGLINE = st.secrets.get("DASHBOARD_TAGLINE", "Decision-grade power market visibility.")

st.markdown(
    """
<style>
.block-container { padding-top: 1.1rem; padding-bottom: 2.4rem; max-width: 1450px; }
h1, h2, h3 { letter-spacing: -0.02em; }
hr { margin: 0.9rem 0 1.1rem 0; border-top: 1px solid rgba(49, 51, 63, 0.12); }
.brandbar { display:flex; align-items:flex-start; justify-content:space-between; gap: 16px; margin-bottom: 10px; }
.brand-name { font-size: 0.95rem; font-weight: 700; letter-spacing: 0.04em; text-transform: uppercase; color: rgba(49, 51, 63, 0.82); }
.brand-title { font-size: 2.05rem; font-weight: 850; letter-spacing: -0.03em; margin-top: 2px; }
.brand-tagline { font-size: 1rem; color: rgba(49, 51, 63, 0.70); }
.pill { display:inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(49, 51, 63, 0.06);
        border: 1px solid rgba(49, 51, 63, 0.10); font-size: 0.85rem; color: rgba(49, 51, 63, 0.75); }
.card { border: 1px solid rgba(49, 51, 63, 0.12); border-radius: 14px; padding: 14px 16px;
        background: rgba(255,255,255,0.90); box-shadow: 0 6px 18px rgba(0,0,0,0.05); }
.card-title { font-size: 0.9rem; color: rgba(49, 51, 63, 0.70); margin-bottom: 6px; }
.card-value { font-size: 1.65rem; font-weight: 800; }
.card-sub { font-size: 0.85rem; color: rgba(49, 51, 63, 0.65); margin-top: 6px; }
.insight { border-left: 4px solid rgba(49, 51, 63, 0.28); padding: 10px 12px; margin-top: 10px;
          border-radius: 10px; background: rgba(49, 51, 63, 0.04); color: rgba(49, 51, 63, 0.88); font-size: 0.95rem; }
.footer { margin-top: 18px; font-size: 0.85rem; color: rgba(49, 51, 63, 0.60); }
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
<div class="brandbar">
  <div>
    <div class="brand-name">{COMPANY_NAME}</div>
    <div class="brand-title">ISO LMP Dashboard — Day-Ahead & Real-Time</div>
    <div class="brand-tagline">{TAGLINE}</div>
  </div>
  <div style="text-align:right;">
    <div class="pill">Trader view • LMP / Spreads / Volatility</div><br/>
    <div class="pill">Source: CAISO OASIS (public)</div>
  </div>
</div>
<hr/>
""",
    unsafe_allow_html=True,
)

# =========================
# UI HELPERS
# =========================
def kpi_card(title: str, value: str, sub: str = ""):
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

def insight_box(text: str):
    st.markdown(f'<div class="insight"><b>Insight:</b> {text}</div>', unsafe_allow_html=True)

def rolling_vol(series: pd.Series, window: int = 24):
    return series.rolling(window, min_periods=max(6, window // 2)).std()

# =========================
# CAISO OASIS PULL (robust)
# =========================
OASIS_URL = "https://oasis.caiso.com/oasisapi/SingleZip"

def _fmt_oasis(dt_utc: datetime) -> str:
    dt_utc = dt_utc.astimezone(timezone.utc)
    return dt_utc.strftime("%Y%m%dT%H:%M-0000")

def _extract_zip_csv(content: bytes) -> pd.DataFrame:
    z = zipfile.ZipFile(io.BytesIO(content))
    csv_name = next((n for n in z.namelist() if n.lower().endswith(".csv")), None)
    if not csv_name:
        return pd.DataFrame()
    raw = z.read(csv_name)
    return pd.read_csv(io.BytesIO(raw))

def _normalize_lmp(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    # Timestamp column candidates commonly seen in CAISO CSV
    ts_col = None
    for c in ["OPRENDTIME_GMT", "INTERVALENDTIME_GMT", "STARTTIME_GMT", "ENDTIME_GMT"]:
        if c in df.columns:
            ts_col = c
            break

    if not ts_col:
        # fallback: any TIME-ish column
        for c in df.columns:
            if "TIME" in c.upper():
                ts_col = c
                break

    if not ts_col:
        return pd.DataFrame()

    df["ts"] = pd.to_datetime(df[ts_col], errors="coerce", utc=True)

    # LMP column is usually LMP
    lmp_col = "LMP" if "LMP" in df.columns else None
    if not lmp_col:
        # fallback: any column ending with LMP
        for c in df.columns:
            if c.upper().endswith("LMP"):
                lmp_col = c
                break

    if not lmp_col:
        return pd.DataFrame()

    df["lmp"] = pd.to_numeric(df[lmp_col], errors="coerce")

    node_col = None
    for c in ["NODE", "PNODE", "APNODE", "PNODE_ID", "APNODE_ID"]:
        if c in df.columns:
            node_col = c
            break
    if not node_col:
        # sometimes "NODE" isn't present; try "SOURCE"
        node_col = "SOURCE" if "SOURCE" in df.columns else None

    df["node"] = df[node_col].astype(str) if node_col else "CAISO"

    out = df.dropna(subset=["ts", "lmp"]).sort_values("ts")[["ts", "node", "lmp"]].reset_index(drop=True)
    return out

@st.cache_data(ttl=600, show_spinner=False)
def fetch_caiso_trade_day(market_run_id: str, trade_day_start_utc: datetime, nodes_csv: str) -> pd.DataFrame:
    """
    Pull ONE trade day (07:00 UTC to next 07:00 UTC) — CAISO example style.
    - DAM hourly: queryname=PRC_LMP, version=12
    - RTM 5-min: queryname=PRC_INTVL_LMP, version=2
    """
    is_dam = market_run_id == "DAM"
    queryname = "PRC_LMP" if is_dam else "PRC_INTVL_LMP"
    version = 12 if is_dam else 2  # common working versions in the wild

    start = trade_day_start_utc
    end = trade_day_start_utc + timedelta(days=1)

    params = {
        "resultformat": 6,  # CSV
        "queryname": queryname,
        "version": version,
        "market_run_id": market_run_id,
        "startdatetime": _fmt_oasis(start),
        "enddatetime": _fmt_oasis(end),
    }

    nodes_csv = (nodes_csv or "").strip()
    if nodes_csv:
        params["node"] = nodes_csv
    else:
        # If user leaves nodes blank, pull ALL (guardrails: still only one trade day)
        params["grp_type"] = "ALL"

    r = requests.get(OASIS_URL, params=params, timeout=60)
    r.raise_for_status()

    raw_df = _extract_zip_csv(r.content)
    return _normalize_lmp(raw_df)

@st.cache_data(ttl=600, show_spinner=False)
def fetch_caiso_window(market_run_id: str, lookback_days: int, nodes_csv: str) -> pd.DataFrame:
    """
    Fetch multiple trade days by looping day-by-day.
    This avoids "no data" caused by non-aligned windows.
    """
    now_utc = datetime.now(timezone.utc)

    # Align to most recent trade-day boundary at 07:00 UTC
    boundary = now_utc.replace(hour=7, minute=0, second=0, microsecond=0)
    if now_utc < boundary:
        boundary = boundary - timedelta(days=1)

    frames = []
    for i in range(lookback_days):
        day_start = boundary - timedelta(days=i)
        df_day = fetch_caiso_trade_day(market_run_id, day_start, nodes_csv)
        if not df_day.empty:
            frames.append(df_day)

    if not frames:
        return pd.DataFrame()

    df = pd.concat(frames, ignore_index=True).drop_duplicates()
    return df.sort_values("ts").reset_index(drop=True)

# =========================
# SIDEBAR CONTROLS
# =========================
st.sidebar.header("Controls")
market = st.sidebar.selectbox("Market", ["Day-Ahead (DAM, hourly)", "Real-Time (RTM, 5-min)"])
market_run_id = "DAM" if "Day-Ahead" in market else "RTM"

lookback = st.sidebar.selectbox("Lookback window", ["1 day", "3 days", "7 days"], index=0)
lookback_days = {"1 day": 1, "3 days": 3, "7 days": 7}[lookback]

st.sidebar.subheader("CAISO nodes (comma-separated)")
st.sidebar.caption("Use known APNodes/DLAP/TH nodes. Defaults are valid examples.")

default_nodes = "TH_NP15_GEN-APND,DLAP_SCE-APND,DLAP_SDGE-APND"
nodes_csv = st.sidebar.text_input("Nodes", value=default_nodes)

# =========================
# LOAD DATA
# =========================
with st.spinner("Loading CAISO LMP data..."):
    df = fetch_caiso_window(market_run_id=market_run_id, lookback_days=lookback_days, nodes_csv=nodes_csv)

if df.empty:
    st.error(
        "No data returned. Most common causes:\n"
        "• Node names are invalid/blank (try the defaults)\n"
        "• Too many nodes / too large window\n"
        "• Try switching DAM↔RTM\n"
    )
    st.stop()

iso_label = f"CAISO {market_run_id}"

# =========================
# KPI ROW
# =========================
latest_ts = df["ts"].max()
latest_slice = df[df["ts"] == latest_ts]
latest_median = latest_slice["lmp"].median() if not latest_slice.empty else df["lmp"].iloc[-1]
avg_lmp = df["lmp"].mean()
p95 = df["lmp"].quantile(0.95)
vol = rolling_vol(df["lmp"], window=24).iloc[-1] if len(df) >= 24 else rolling_vol(df["lmp"], window=max(6, len(df)//2)).iloc[-1]

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("Latest LMP (Median)", f"${latest_median:,.2f}", sub=f"{iso_label} • {latest_ts.strftime('%Y-%m-%d %H:%M UTC')}")
with k2:
    kpi_card("Average (Window)", f"${avg_lmp:,.2f}", sub=f"Last {lookback_days} trade day(s)")
with k3:
    kpi_card("95th Percentile", f"${p95:,.2f}", sub="Spike threshold proxy")
with k4:
    kpi_card("Volatility (Rolling)", f"{(vol if pd.notna(vol) else 0):,.2f}", sub="Std dev proxy")

st.markdown("<hr/>", unsafe_allow_html=True)

# =========================
# 1) TREND + INSIGHT
# =========================
st.subheader("LMP Trend")
fig_trend = px.line(df, x="ts", y="lmp", color="node", title=f"{iso_label} LMP — Trend by Node")
st.plotly_chart(fig_trend, use_container_width=True)

if latest_slice["lmp"].nunique() > 1:
    hi = latest_slice.sort_values("lmp", ascending=False).iloc[0]
    lo = latest_slice.sort_values("lmp", ascending=True).iloc[0]
    spread = hi["lmp"] - lo["lmp"]
    insight_box(
        f"Latest timestamp spread is **${spread:,.2f}** (high: **{hi['node']} ${hi['lmp']:,.2f}**, low: **{lo['node']} ${lo['lmp']:,.2f}**). "
        "Widening spreads often indicate localized congestion or marginal loss impacts."
    )
else:
    insight_box("Add more nodes to turn this into a spread/congestion monitor (DLAP vs TH is a common trader lens).")

st.markdown("<hr/>", unsafe_allow_html=True)

# =========================
# 2) DISTRIBUTION / SPIKES + INSIGHT
# =========================
st.subheader("Spike & Distribution View")
fig_hist = px.histogram(df, x="lmp", color="node", nbins=50, title=f"{iso_label} LMP Distribution")
st.plotly_chart(fig_hist, use_container_width=True)

spike_rate = (df["lmp"] >= p95).mean() * 100.0
insight_box(
    f"About **{spike_rate:,.1f}%** of intervals in this window are at/above the **95th percentile (${p95:,.2f})**. "
    "If this rises materially week-over-week, desks typically tighten risk limits or widen retail pricing adders."
)

st.markdown("<hr/>", unsafe_allow_html=True)

# =========================
# 3) INTRADAY HEATMAP + INSIGHT
# =========================
st.subheader("Intraday Pattern Heatmap")

heat = df.copy()
heat["hour_ts"] = heat["ts"].dt.floor("H")
heat["hour"] = heat["hour_ts"].dt.hour
heat["date"] = heat["hour_ts"].dt.date
heat_agg = heat.groupby(["node", "date", "hour"], as_index=False)["lmp"].mean()

node_for_heat = st.selectbox("Heatmap node", options=sorted(heat_agg["node"].unique().tolist()))
h = heat_agg[heat_agg["node"] == node_for_heat].copy()
pivot = h.pivot_table(index="hour", columns="date", values="lmp", aggfunc="mean")

fig_heat = px.imshow(pivot, aspect="auto", title=f"Hourly Pattern — {node_for_heat} (avg $/MWh by hour)")
st.plotly_chart(fig_heat, use_container_width=True)

by_hour = h.groupby("hour")["lmp"].mean().sort_values(ascending=False)
peak_hour = int(by_hour.index[0])
peak_val = float(by_hour.iloc[0])
trough_hour = int(by_hour.index[-1])
trough_val = float(by_hour.iloc[-1])

insight_box(
    f"Typical peak hour is **{peak_hour}:00** at **${peak_val:,.2f}**, vs trough around **{trough_hour}:00** at **${trough_val:,.2f}**. "
    "This quickly shows repeating stress hours and helps validate hedging blocks (5x16/7x24 behavior)."
)

st.markdown("<hr/>", unsafe_allow_html=True)

# =========================
# 4) AUDIT TABLE + DOWNLOAD
# =========================
st.subheader("Audit Table (Downloadable)")
st.caption("Decision-grade dashboards stay auditable. Export the raw time series any time.")

show = df.sort_values("ts", ascending=False)
st.dataframe(show, use_container_width=True, height=360)

csv = show.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", data=csv, file_name=f"{iso_label.replace(' ', '_').lower()}_lmp.csv", mime="text/csv")

st.markdown(f'<div class="footer">© {datetime.now().year} {COMPANY_NAME}. Internal use.</div>', unsafe_allow_html=True)
