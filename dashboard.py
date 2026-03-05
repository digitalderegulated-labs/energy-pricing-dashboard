import streamlit as st
import pandas as pd
import requests
import zipfile
import io
import plotly.express as px
from datetime import datetime, timedelta, timezone

# =========================
# CONFIG + BRANDING
# =========================
st.set_page_config(page_title="Power Market Dashboard", layout="wide")

COMPANY_NAME = st.secrets.get("COMPANY_NAME", "Digital Deregulated Labs")
TAGLINE = st.secrets.get("DASHBOARD_TAGLINE", "Decision-grade power market visibility.")
PJM_API_KEY = st.secrets.get("PJM_API_KEY", "")

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
    <div class="pill">Trader view • LMP / Spread / Volatility</div><br/>
    <div class="pill">Source: CAISO OASIS + PJM DataMiner (if enabled)</div>
  </div>
</div>
<hr/>
""",
    unsafe_allow_html=True,
)

# =========================
# HELPERS
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

def _safe_float(x):
    try:
        return float(x)
    except Exception:
        return None

def _rolling_vol(series: pd.Series, window: int):
    return series.rolling(window, min_periods=max(3, window // 2)).std()

# =========================
# CAISO OASIS (PUBLIC) — DA hourly + RT 5-min
# Uses SingleZip + resultformat=6 (CSV) as shown in CAISO examples. :contentReference[oaicite:3]{index=3}
# =========================
@st.cache_data(ttl=600, show_spinner=False)
def fetch_caiso_lmp(market: str, start_utc: datetime, end_utc: datetime, nodes_csv: str):
    """
    market:
      - "DAM" => hourly day-ahead LMP: queryname=PRC_LMP
      - "RTM" => 5-min real-time interval LMP: queryname=PRC_INTVL_LMP
    """
    queryname = "PRC_LMP" if market == "DAM" else "PRC_INTVL_LMP"

    # CAISO expects timestamps like 20250401T07:00-0000
    def fmt(dt: datetime) -> str:
        dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y%m%dT%H:%M-0000")

    params = {
        "queryname": queryname,
        "startdatetime": fmt(start_utc),
        "enddatetime": fmt(end_utc),
        "version": "2",
        "resultformat": "6",  # CSV
        "market_run_id": market,
    }
    # nodes: comma-separated
    if nodes_csv.strip():
        params["node"] = nodes_csv.strip()

    url = "https://oasis.caiso.com/oasisapi/SingleZip"
    r = requests.get(url, params=params, timeout=60)
    r.raise_for_status()

    # Response is a zip
    z = zipfile.ZipFile(io.BytesIO(r.content))
    # take first CSV inside
    csv_name = next((n for n in z.namelist() if n.lower().endswith(".csv")), None)
    if not csv_name:
        return pd.DataFrame()

    raw = z.read(csv_name)
    df = pd.read_csv(io.BytesIO(raw))

    # Normalize expected columns
    # Common columns include: PRC_LMP / PRC_INTVL_LMP fields like OPRENDTIME_GMT, LMP, PNODE, etc.
    # We'll robustly map:
    time_col = "OPR_DT" if "OPR_DT" in df.columns else None
    if "OPRENDTIME_GMT" in df.columns:
        df["ts"] = pd.to_datetime(df["OPRENDTIME_GMT"], errors="coerce", utc=True)
    elif "INTERVALENDTIME_GMT" in df.columns:
        df["ts"] = pd.to_datetime(df["INTERVALENDTIME_GMT"], errors="coerce", utc=True)
    elif time_col:
        df["ts"] = pd.to_datetime(df[time_col], errors="coerce", utc=True)
    else:
        # fallback: find any datetime-like column
        for c in df.columns:
            if "TIME" in c.upper():
                df["ts"] = pd.to_datetime(df[c], errors="coerce", utc=True)
                break

    # Price
    price_col = "LMP" if "LMP" in df.columns else None
    if not price_col:
        # Try other likely column names
        for c in df.columns:
            if c.upper().endswith("LMP"):
                price_col = c
                break
    if price_col:
        df["lmp"] = pd.to_numeric(df[price_col], errors="coerce")

    # Node/location
    node_col = None
    for c in ["PNODE", "APNODE", "NODE", "NODE_NAME", "NODE_ID"]:
        if c in df.columns:
            node_col = c
            break
    if node_col:
        df["node"] = df[node_col].astype(str)

    df = df.dropna(subset=["ts", "lmp"])
    df = df.sort_values("ts")
    return df[["ts", "node", "lmp"]].reset_index(drop=True)

# =========================
# PJM (DataMiner/API Portal) — requires subscription key
# Feeds exist for DA and RT hourly LMPs. :contentReference[oaicite:4]{index=4}
# We'll implement the common api.pjm.com pattern; if the user doesn't provide a key, we skip gracefully.
# =========================
@st.cache_data(ttl=600, show_spinner=False)
def fetch_pjm_lmp(feed: str, start_iso: str, end_iso: str, pnode: str = "WESTERN HUB"):
    """
    feed: "da_hrl_lmps" or "rt_hrl_lmps"
    start_iso/end_iso: e.g. "2026-03-01 00:00"
    """
    if not PJM_API_KEY:
        return pd.DataFrame()

    base = f"https://api.pjm.com/api/v1/{feed}"
    headers = {"Ocp-Apim-Subscription-Key": PJM_API_KEY}

    # Narrow scope: filter to one aggregate/hub-like pnode to avoid huge pulls
    params = {
        "startRow": 1,
        "rowCount": 5000,
        # Many PJM feeds accept datetime filters; exact parameter names can vary by feed definition.
        # We'll try common patterns:
        "datetime_beginning": start_iso,
        "datetime_ending": end_iso,
        "pnode_name": pnode,
    }

    r = requests.get(base, headers=headers, params=params, timeout=60)
    if r.status_code != 200:
        # fail gracefully (show debug in UI)
        return pd.DataFrame({"error": [f"PJM request failed: {r.status_code}"], "text": [r.text[:500]]})

    j = r.json()
    # PJM often returns list under "items"
    items = j.get("items", j if isinstance(j, list) else [])
    df = pd.DataFrame(items)
    if df.empty:
        return df

    # Try to locate timestamp and LMP columns
    ts_col = None
    for c in df.columns:
        if "datetime" in c.lower():
            ts_col = c
            break
    if ts_col:
        df["ts"] = pd.to_datetime(df[ts_col], errors="coerce")

    lmp_col = None
    for c in df.columns:
        if c.lower() in ["lmp", "total_lmp", "lmp_total", "rt_lmp", "da_lmp"] or "lmp" in c.lower():
            lmp_col = c
            break
    if lmp_col:
        df["lmp"] = pd.to_numeric(df[lmp_col], errors="coerce")

    node_col = None
    for c in ["pnode_name", "pnode_id", "node", "name"]:
        if c in df.columns:
            node_col = c
            break
    df["node"] = df[node_col].astype(str) if node_col else "PJM"

    df = df.dropna(subset=["ts", "lmp"]).sort_values("ts")
    return df[["ts", "node", "lmp"]].reset_index(drop=True)

# =========================
# SIDEBAR CONTROLS
# =========================
st.sidebar.header("Controls")
st.sidebar.caption("Keep it trader-simple: pick ISO, market, window, and hub/nodes.")

iso = st.sidebar.selectbox("ISO", ["CAISO (OASIS)", "PJM (DataMiner)"])

market = st.sidebar.selectbox("Market", ["Day-Ahead (DAM)", "Real-Time (RTM)"])
market_code = "DAM" if "Day-Ahead" in market else "RTM"

lookback = st.sidebar.selectbox("Lookback window", ["1 day", "3 days", "7 days"], index=1)
days = {"1 day": 1, "3 days": 3, "7 days": 7}[lookback]

# Time window (UTC)
now_utc = datetime.now(timezone.utc)
start_utc = now_utc - timedelta(days=days)
end_utc = now_utc

# ISO-specific selectors
if iso.startswith("CAISO"):
    st.sidebar.subheader("CAISO nodes (comma-separated)")
    st.sidebar.caption("Example: TH_NP15_GEN-APND,DLAP_SCE-APND")
    caiso_nodes = st.sidebar.text_input("Nodes", value="TH_NP15_GEN-APND,DLAP_SCE-APND")
else:
    st.sidebar.subheader("PJM hub/pnode")
    st.sidebar.caption("Use an aggregate/hub name to avoid huge pulls.")
    pjm_pnode = st.sidebar.text_input("Pnode name", value="WESTERN HUB")

# =========================
# LOAD DATA
# =========================
with st.spinner("Loading ISO LMP data..."):
    if iso.startswith("CAISO"):
        df = fetch_caiso_lmp(market=market_code, start_utc=start_utc, end_utc=end_utc, nodes_csv=caiso_nodes)
        iso_label = f"CAISO {market_code}"
    else:
        feed = "da_hrl_lmps" if market_code == "DAM" else "rt_hrl_lmps"
        # PJM time format often expects local/ISO strings; keep it simple:
        start_iso = (now_utc - timedelta(days=days)).strftime("%Y-%m-%d %H:%M")
        end_iso = now_utc.strftime("%Y-%m-%d %H:%M")
        df = fetch_pjm_lmp(feed=feed, start_iso=start_iso, end_iso=end_iso, pnode=pjm_pnode)
        iso_label = f"PJM {market_code}"

# Handle PJM missing key
if iso.startswith("PJM") and not PJM_API_KEY:
    st.warning("PJM is enabled in the dashboard, but no PJM_API_KEY is set in Streamlit secrets. Add it to use PJM DA/RT LMP feeds.")
    st.stop()

# Handle errors returned as dataframe
if "error" in df.columns:
    st.error(df["error"].iloc[0])
    st.code(df.get("text", pd.Series([""])).iloc[0] if not df.empty else "")
    st.stop()

if df.empty:
    st.error("No data returned for that window/nodes. Try a shorter window, different nodes/hub, or switch market.")
    st.stop()

# =========================
# KPI ROW (PowerBI-style)
# =========================
latest_ts = df["ts"].max()
latest_slice = df[df["ts"] == latest_ts]
latest_median = latest_slice["lmp"].median() if not latest_slice.empty else df["lmp"].iloc[-1]

avg_lmp = df["lmp"].mean()
p95 = df["lmp"].quantile(0.95)
vol = _rolling_vol(df["lmp"], window=min(24, max(6, len(df) // 10))).iloc[-1]  # crude, but stable

k1, k2, k3, k4 = st.columns(4)
with k1:
    kpi_card("Latest LMP (Median)", f"${latest_median:,.2f}", sub=f"{iso_label} • {latest_ts.strftime('%Y-%m-%d %H:%M UTC')}")
with k2:
    kpi_card("Average (Window)", f"${avg_lmp:,.2f}", sub=f"Last {days} day(s)")
with k3:
    kpi_card("95th Percentile", f"${p95:,.2f}", sub="Spike-prone threshold")
with k4:
    kpi_card("Volatility (Rolling)", f"{(vol if pd.notna(vol) else 0):,.2f}", sub="Std dev proxy")

st.markdown("<hr/>", unsafe_allow_html=True)

# =========================
# 1) TREND CHART + INSIGHT
# =========================
st.subheader("LMP Trend")
fig_trend = px.line(
    df,
    x="ts",
    y="lmp",
    color="node",
    title=f"{iso_label} LMP — Trend by Node/Hub",
)
st.plotly_chart(fig_trend, use_container_width=True)

# Insight: who leads latest, spread
if latest_slice["lmp"].nunique() > 1:
    hi = latest_slice.sort_values("lmp", ascending=False).iloc[0]
    lo = latest_slice.sort_values("lmp", ascending=True).iloc[0]
    spread = hi["lmp"] - lo["lmp"]
    insight_box(
        f"At the latest timestamp, **{hi['node']}** is highest at **${hi['lmp']:,.2f}** and **{lo['node']}** is lowest at "
        f"**${lo['lmp']:,.2f}** (spread **${spread:,.2f}**). Spreads widening typically signal localized congestion or loss components."
    )
else:
    insight_box("Trend confirms the price path for the selected node/hub. Add more nodes to turn this into a spread/congestion monitor.")

st.markdown("<hr/>", unsafe_allow_html=True)

# =========================
# 2) DISTRIBUTION / SPIKES + INSIGHT
# =========================
st.subheader("Spike & Distribution View")
fig_hist = px.histogram(
    df,
    x="lmp",
    color="node",
    nbins=50,
    title=f"{iso_label} LMP Distribution — Where prices cluster vs spike",
)
st.plotly_chart(fig_hist, use_container_width=True)

spike_threshold = p95
spike_rate = (df["lmp"] >= spike_threshold).mean() * 100.0
insight_box(
    f"**Spike frequency:** {spike_rate:,.1f}% of intervals are at/above the **95th percentile (${spike_threshold:,.2f})** in this window. "
    "If this rate rises week-over-week, traders typically tighten risk limits or widen retail margins (depending on book)."
)

st.markdown("<hr/>", unsafe_allow_html=True)

# =========================
# 3) HOURLY HEATMAP (PowerBI-like) + INSIGHT
# For RT 5-min, we bucket to hour to make it readable.
# =========================
st.subheader("Intraday Pattern Heatmap")

heat = df.copy()
heat["hour_ts"] = heat["ts"].dt.floor("H")
heat["hour"] = heat["hour_ts"].dt.hour
heat["date"] = heat["hour_ts"].dt.date

heat_agg = heat.groupby(["node", "date", "hour"], as_index=False)["lmp"].mean()

# Choose one node for heatmap clarity
node_for_heat = st.selectbox("Heatmap node", options=sorted(heat_agg["node"].unique().tolist()))
h = heat_agg[heat_agg["node"] == node_for_heat].copy()

pivot = h.pivot_table(index="hour", columns="date", values="lmp", aggfunc="mean")
fig_heat = px.imshow(pivot, aspect="auto", title=f"Hourly Pattern — {node_for_heat} (avg $/MWh by hour)")
st.plotly_chart(fig_heat, use_container_width=True)

# Insight: peak hour and typical ramp
if not h.empty:
    by_hour = h.groupby("hour")["lmp"].mean().sort_values(ascending=False)
    peak_hour = int(by_hour.index[0])
    peak_val = float(by_hour.iloc[0])
    trough_hour = int(by_hour.index[-1])
    trough_val = float(by_hour.iloc[-1])
    insight_box(
        f"**Typical peak hour:** {peak_hour}:00 at **${peak_val:,.2f}** vs trough around {trough_hour}:00 at **${trough_val:,.2f}**. "
        "This is a fast way to spot repeated morning/evening stress and validate hedging blocks (ATC, 5x16/7x24 behavior)."
    )

st.markdown("<hr/>", unsafe_allow_html=True)

# =========================
# 4) AUDIT TABLE + EXPORT
# =========================
st.subheader("Audit Table (Downloadable)")
st.caption("This keeps the dashboard decision-grade — you can validate the source series quickly.")

show = df.sort_values("ts", ascending=False)
st.dataframe(show, use_container_width=True, height=360)

csv = show.to_csv(index=False).encode("utf-8")
st.download_button("Download CSV", data=csv, file_name=f"{iso_label.replace(' ', '_').lower()}_lmp.csv", mime="text/csv")

st.markdown(f'<div class="footer">© {datetime.now().year} {COMPANY_NAME}. Internal use.</div>', unsafe_allow_html=True)
