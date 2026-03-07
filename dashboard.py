import streamlit as st
import pandas as pd
import requests
import plotly.express as px
import plotly.graph_objects as go
import zipfile
import io
from datetime import datetime, timedelta, timezone

# =========================================================
# PAGE + BRAND (ALWAYS SHOWS EVEN IF DATA FAILS)
# =========================================================
st.set_page_config(page_title="ISO LMP Dashboard", layout="wide")

COMPANY_NAME = st.secrets.get("COMPANY_NAME", "Digital Deregulated Labs")
TAGLINE = st.secrets.get("DASHBOARD_TAGLINE", "Decision-grade power market visibility.")
BRAND_LINE = st.secrets.get("BRAND_LINE", "Market Intelligence • ISO LMP • Trader + Executive Views")

st.markdown(
    """
<style>
.block-container { padding-top: 1.1rem; padding-bottom: 2.4rem; max-width: 1480px; }
h1, h2, h3 { letter-spacing: -0.02em; }
hr { margin: 0.9rem 0 1.1rem 0; border-top: 1px solid rgba(49, 51, 63, 0.12); }

.brandbar { display:flex; align-items:flex-start; justify-content:space-between; gap: 16px; margin-bottom: 10px; }
.brand-name { font-size: 0.95rem; font-weight: 750; letter-spacing: 0.04em; text-transform: uppercase; color: rgba(49, 51, 63, 0.82); }
.brand-title { font-size: 2.05rem; font-weight: 900; letter-spacing: -0.03em; margin-top: 2px; }
.brand-tagline { font-size: 1rem; color: rgba(49, 51, 63, 0.70); margin-top: 2px; }
.pill { display:inline-block; padding: 6px 10px; border-radius: 999px; background: rgba(49, 51, 63, 0.06);
        border: 1px solid rgba(49, 51, 63, 0.10); font-size: 0.85rem; color: rgba(49, 51, 63, 0.75); }

.kpi-row { margin-top: 6px; }
.card { border: 1px solid rgba(49, 51, 63, 0.12); border-radius: 14px; padding: 14px 16px;
        background: rgba(255,255,255,0.92); box-shadow: 0 6px 18px rgba(0,0,0,0.05); }
.card-title { font-size: 0.9rem; color: rgba(49, 51, 63, 0.70); margin-bottom: 6px; }
.card-value { font-size: 1.65rem; font-weight: 850; }
.card-sub { font-size: 0.85rem; color: rgba(49, 51, 63, 0.65); margin-top: 6px; }

.insight { border-left: 4px solid rgba(49, 51, 63, 0.30); padding: 10px 12px; margin-top: 10px;
          border-radius: 10px; background: rgba(49, 51, 63, 0.04); color: rgba(49, 51, 63, 0.88); font-size: 0.95rem; }
.subtle { color: rgba(49, 51, 63, 0.65); font-size: 0.92rem; }
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
    <div class="subtle">{BRAND_LINE}</div>
  </div>
  <div style="text-align:right;">
    <div class="pill">Enterprise PowerBI-style</div><br/>
    <div class="pill">Source: CAISO OASIS (public)</div>
  </div>
</div>
<hr/>
""",
    unsafe_allow_html=True,
)

# =========================================================
# UI HELPERS
# =========================================================
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

# =========================================================
# CAISO OASIS SETTINGS (REAL API)
# =========================================================
OASIS_URL = "https://oasis.caiso.com/oasisapi/SingleZip"

# Clean, non-breakable dropdowns (friendly labels -> tokens to match)
LOCATIONS = {
    "NP15 Hub (North CA)": ["NP15"],
    "SP15 Hub (South CA)": ["SP15"],
    "ZP26 Hub (Central CA)": ["ZP26"],
    "SCE DLAP (Load)": ["DLAP_SCE", "SCE"],
    "SDGE DLAP (Load)": ["DLAP_SDGE", "SDGE"],
    "PGE DLAP (Load)": ["DLAP_PGE", "PGE"],
}

def fmt_oasis(dt_utc: datetime) -> str:
    dt_utc = dt_utc.astimezone(timezone.utc)
    return dt_utc.strftime("%Y%m%dT%H:%M-0000")

def build_trade_day_window_utc(days_back: int = 0):
    """
    CAISO trade day boundary is commonly represented as 07:00 UTC in their examples.
    We'll always request full trade day(s): 07:00 -> next day 07:00.
    """
    now_utc = datetime.now(timezone.utc)
    boundary = now_utc.replace(hour=7, minute=0, second=0, microsecond=0)
    if now_utc < boundary:
        boundary -= timedelta(days=1)
    start = boundary - timedelta(days=days_back)
    end = start + timedelta(days=1)
    return start, end

def unzip_first_csv(content: bytes) -> tuple[pd.DataFrame, list[str]]:
    z = zipfile.ZipFile(io.BytesIO(content))
    names = z.namelist()
    csv_name = next((n for n in names if n.lower().endswith(".csv")), None)
    if not csv_name:
        return pd.DataFrame(), names
    raw = z.read(csv_name)
    return pd.read_csv(io.BytesIO(raw)), names

def normalize_caiso(df: pd.DataFrame) -> pd.DataFrame:
    """
    Robust normalization:
    - timestamp columns vary
    - price column for PRC_LMP is often MW (not LMP)
    - other services may use PRC or LMP
    """
    if df is None or df.empty:
        return pd.DataFrame()

    # timestamp
    ts_col = None
    for c in ["OPRENDTIME_GMT", "INTERVALENDTIME_GMT", "STARTTIME_GMT", "ENDTIME_GMT"]:
        if c in df.columns:
            ts_col = c
            break
    if not ts_col:
        for c in df.columns:
            if "TIME" in c.upper():
                ts_col = c
                break
    if not ts_col:
        return pd.DataFrame()

    out = df.copy()
    out["ts"] = pd.to_datetime(out[ts_col], errors="coerce", utc=True)

    # price column candidates (important: MW is common)
    price_col = None
    for c in ["LMP", "MW", "PRC", "VALUE", "PRICE"]:
        if c in out.columns:
            price_col = c
            break
    if not price_col:
        # fallback: any col with lmp/prc/mw
        for c in out.columns:
            cu = c.upper()
            if cu.endswith("LMP") or cu.endswith("PRC") or cu == "MW":
                price_col = c
                break
    if not price_col:
        return pd.DataFrame()

    out["lmp"] = pd.to_numeric(out[price_col], errors="coerce")

    # node-like identifier
    node_col = None
    for c in ["NODE", "PNODE", "APNODE", "PNODE_NAME", "APNODE_NAME", "PNODE_ID", "APNODE_ID"]:
        if c in out.columns:
            node_col = c
            break
    if node_col:
        out["node"] = out[node_col].astype(str)
    else:
        # last resort: create one series label
        out["node"] = "CAISO"

    out = out.dropna(subset=["ts", "lmp"]).sort_values("ts")[["ts", "node", "lmp"]].reset_index(drop=True)
    return out

@st.cache_data(ttl=600, show_spinner=False)
def fetch_caiso(market_run_id: str, lookback_days: int, debug: bool = False):
    """
    Uses CAISO's documented approach:
    - resultformat=6 (CSV)
    - trade-day window 07:00 UTC to next 07:00 UTC
    - grp_type=ALL allowed for retrieving ALL nodes (one trade day at a time)
    """
    is_dam = market_run_id == "DAM"
    queryname = "PRC_LMP" if is_dam else "PRC_INTVL_LMP"
    version = 12 if is_dam else 2  # aligns with known practice

    frames = []
    debug_rows = []

    for i in range(lookback_days):
        start, end = build_trade_day_window_utc(days_back=i)

        params = {
            "queryname": queryname,
            "startdatetime": fmt_oasis(start),
            "enddatetime": fmt_oasis(end),
            "version": version,
            "resultformat": 6,
            "market_run_id": market_run_id,
            "grp_type": "ALL",  # documented option
        }

        r = requests.get(OASIS_URL, params=params, timeout=60)
        url = r.url

        # capture debug even if request fails
        if debug:
            debug_rows.append({
                "trade_day_start_utc": start.isoformat(),
                "status": r.status_code,
                "bytes": len(r.content) if r.content else 0,
                "url": url
            })

        if r.status_code != 200 or not r.content:
            continue

        raw_df, zip_names = unzip_first_csv(r.content)
        norm = normalize_caiso(raw_df)

        if debug:
            debug_rows[-1]["zip_files"] = ", ".join(zip_names[:5]) + ("..." if len(zip_names) > 5 else "")
            debug_rows[-1]["raw_cols"] = ", ".join(list(raw_df.columns)[:12]) + ("..." if raw_df is not None and raw_df.shape[1] > 12 else "")
            debug_rows[-1]["raw_rows"] = 0 if raw_df is None else int(raw_df.shape[0])
            debug_rows[-1]["normalized_rows"] = int(norm.shape[0]) if norm is not None else 0

        if norm is not None and not norm.empty:
            frames.append(norm)

    df = pd.concat(frames, ignore_index=True).drop_duplicates().sort_values("ts").reset_index(drop=True) if frames else pd.DataFrame()
    dbg = pd.DataFrame(debug_rows) if debug_rows else pd.DataFrame()
    return df, dbg

def filter_location(df: pd.DataFrame, location_key: str) -> pd.DataFrame:
    tokens = LOCATIONS.get(location_key, [])
    if df.empty:
        return df
    s = df["node"].astype(str)
    mask = False
    for t in tokens:
        mask = mask | s.str.contains(t, case=False, na=False)
    sub = df[mask].copy()
    # fallback if tokens don’t exist in the returned node list
    if sub.empty:
        top = df["node"].value_counts().head(3).index.tolist()
        sub = df[df["node"].isin(top)].copy()
    return sub

# =========================================================
# CONTROLS (SIMPLE, ENTERPRISE)
# =========================================================
st.sidebar.header("Controls")

market_label = st.sidebar.selectbox("Market", ["Day-Ahead (Hourly)", "Real-Time (5-min)"])
market_run_id = "DAM" if "Day-Ahead" in market_label else "RTM"

lookback_label = st.sidebar.selectbox("Lookback", ["1 day", "3 days", "7 days"], index=0)
lookback_days = {"1 day": 1, "3 days": 3, "7 days": 7}[lookback_label]

location_key = st.sidebar.selectbox("Location", list(LOCATIONS.keys()), index=0)

# Keep UI stable: optional advanced toggle
show_debug = st.sidebar.toggle("Show Data QA (recommended while building)", value=True)

# =========================================================
# LOAD DATA (AND DO NOT SILENTLY FAIL)
# =========================================================
with st.spinner("Pulling CAISO OASIS data..."):
    df_all, dbg = fetch_caiso(market_run_id=market_run_id, lookback_days=lookback_days, debug=show_debug)

df = filter_location(df_all, location_key) if not df_all.empty else pd.DataFrame()

# =========================================================
# TABS: EXEC + TRADER + SPREADS + DATA QA
# =========================================================
tab_exec, tab_trader, tab_spreads, tab_qa = st.tabs(["Executive View", "Trader View", "Spreads & Risk", "Data QA"])

# ---------------------------
# DATA GUARDRAIL MESSAGE
# ---------------------------
if df_all.empty:
    # Header stays, tabs still render. No more “where is my company info / insights?”
    with tab_exec:
        st.error("No data returned from CAISO OASIS for this market/window.")
        st.write("This is almost always one of these: (1) CAISO returned different columns than expected, (2) the zip contained no CSV, or (3) the request is not aligned to a trade day. Open **Data QA** to see the exact URL and columns returned.")
    with tab_trader:
        st.info("Waiting for data… open **Data QA** to verify the API response.")
    with tab_spreads:
        st.info("Spreads require data from at least one location. Open **Data QA**.")
    with tab_qa:
        st.subheader("Data QA")
        st.caption("This is the truth source: what CAISO returned, and the exact URL used.")
        if not dbg.empty:
            st.dataframe(dbg, use_container_width=True, height=340)
            st.write("Tip: If status=200 but normalized_rows=0, it usually means the price column is not `LMP` (often `MW` for DAM).")
        else:
            st.write("No debug rows captured.")
    st.stop()

# =========================================================
# COMMON METRICS
# =========================================================
latest_ts = df["ts"].max()
latest_slice = df[df["ts"] == latest_ts]
latest_median = latest_slice["lmp"].median() if not latest_slice.empty else df["lmp"].iloc[-1]
avg_lmp = df["lmp"].mean()
p95 = df["lmp"].quantile(0.95)
vol = rolling_vol(df["lmp"], window=24).iloc[-1] if len(df) >= 24 else rolling_vol(df["lmp"], window=max(6, len(df)//2)).iloc[-1]
spike_rate = (df["lmp"] >= p95).mean() * 100.0

# =========================================================
# EXECUTIVE VIEW (NON-TRADER FRIENDLY)
# =========================================================
with tab_exec:
    st.subheader("Executive Summary — Price Level, Spikes, and Pattern")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Latest Price (Median)", f"${latest_median:,.2f}", f"{location_key} • {latest_ts.strftime('%Y-%m-%d %H:%M UTC')}")
    with c2:
        kpi_card("Average (Window)", f"${avg_lmp:,.2f}", f"{lookback_days} trade day(s)")
    with c3:
        kpi_card("Spike Threshold (95th)", f"${p95:,.2f}", "High-price risk marker")
    with c4:
        kpi_card("Spike Frequency", f"{spike_rate:,.1f}%", "Share of intervals above 95th")

    st.markdown("<hr/>", unsafe_allow_html=True)

    st.markdown("### Price Trend ")
    fig = px.line(df, x="ts", y="lmp", color="node", title="Price over time (selected location filter)")
    st.plotly_chart(fig, use_container_width=True)

    insight_box(
        f"Prices averaged **${avg_lmp:,.2f}** over the window. "
        f"Spikes (≥95th percentile) occurred **{spike_rate:,.1f}%** of the time—this is a quick signal of operational stress or risk-on periods."
    )

    st.markdown("<hr/>", unsafe_allow_html=True)

    st.markdown("### Distribution ")
    fig2 = px.histogram(df, x="lmp", nbins=50, color="node", title="Where prices cluster vs spike")
    st.plotly_chart(fig2, use_container_width=True)

    insight_box(
        "If the distribution has a long right tail, procurement and retail pricing should assume "
        "a higher probability of stress events (and should test margin adequacy under spikes)."
    )

# =========================================================
# TRADER VIEW (TERMINAL-LIKE)
# =========================================================
with tab_trader:
    st.subheader("Trader View — LMP, Volatility, and Intraday Structure")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Latest LMP (Median)", f"${latest_median:,.2f}", f"{location_key}")
    with c2:
        kpi_card("Volatility (Rolling)", f"{(vol if pd.notna(vol) else 0):,.2f}", "Std dev proxy")
    with c3:
        kpi_card("95th Percentile", f"${p95:,.2f}", "Spike proxy")
    with c4:
        kpi_card("Lookback", f"{lookback_days}d", f"{market_label}")

    st.markdown("<hr/>", unsafe_allow_html=True)

    st.markdown("### LMP Trend (multi-series)")
    fig = px.line(df, x="ts", y="lmp", color="node", title="LMP time series")
    st.plotly_chart(fig, use_container_width=True)

    if latest_slice["node"].nunique() > 1:
        hi = latest_slice.sort_values("lmp", ascending=False).iloc[0]
        lo = latest_slice.sort_values("lmp", ascending=True).iloc[0]
        spread = hi["lmp"] - lo["lmp"]
        insight_box(
            f"Latest cross-series spread is **${spread:,.2f}** (high: **{hi['node']}**, low: **{lo['node']}**). "
            "Widening spreads often track congestion/loss impacts or local stress."
        )
    else:
        insight_box("Add more location scope later if you want a dedicated spread monitor. This is the single-location terminal view.")

    st.markdown("<hr/>", unsafe_allow_html=True)

    st.markdown("### Intraday Heatmap (pattern recognition)")
    heat = df.copy()
    heat["hour_ts"] = heat["ts"].dt.floor("H")
    heat["hour"] = heat["hour_ts"].dt.hour
    heat["date"] = heat["hour_ts"].dt.date
    heat_agg = heat.groupby(["node", "date", "hour"], as_index=False)["lmp"].mean()

    node_for_heat = st.selectbox("Series (Heatmap)", options=sorted(heat_agg["node"].unique().tolist()))
    h = heat_agg[heat_agg["node"] == node_for_heat].copy()
    pivot = h.pivot_table(index="hour", columns="date", values="lmp", aggfunc="mean")
    fig_h = px.imshow(pivot, aspect="auto", title=f"Hourly pattern — {node_for_heat}")
    st.plotly_chart(fig_h, use_container_width=True)

    by_hour = h.groupby("hour")["lmp"].mean().sort_values(ascending=False)
    peak_hour = int(by_hour.index[0])
    peak_val = float(by_hour.iloc[0])
    insight_box(
        f"Typical peak hour is **{peak_hour}:00** at **${peak_val:,.2f}**. "
        "This is your fast read on recurring stress hours and hedging block behavior."
    )

# =========================================================
# SPREADS & RISK (TRADER-HEAVY)
# =========================================================
with tab_spreads:
    st.subheader("Spreads & Risk — Hub vs Load / Multi-series")

    # Build a simple multi-series pivot for spread math
    piv = df.pivot_table(index="ts", columns="node", values="lmp", aggfunc="mean").sort_index()

    st.markdown("### Cross-series spread (highest - lowest)")
    if piv.shape[1] >= 2:
        spread_series = piv.max(axis=1) - piv.min(axis=1)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=spread_series.index, y=spread_series.values, mode="lines", name="Spread"))
        fig.update_layout(title="Spread proxy (max node - min node)", xaxis_title="Time", yaxis_title="$ / MWh")
        st.plotly_chart(fig, use_container_width=True)

        insight_box(
            "This is a quick congestion/stress proxy: when the spread widens, location risk matters more "
            "and fixed-price positions become more fragile."
        )
    else:
        st.info("Not enough series to compute spreads. Choose a location that yields multiple node series, or expand the model later.")

    st.markdown("<hr/>", unsafe_allow_html=True)

    st.markdown("### Risk snapshot (percentiles)")
    pct = df.groupby("node")["lmp"].quantile([0.5, 0.9, 0.95]).unstack()
    pct.columns = ["P50", "P90", "P95"]
    st.dataframe(pct.sort_values("P95", ascending=False), use_container_width=True)

    insight_box(
        "Nodes with higher P95 are your stress-prone locations. "
        "That’s where basis risk or congestion sensitivity is likely to show up first."
    )

# =========================================================
# DATA QA (ENTERPRISE-TRUST FEATURE)
# =========================================================
with tab_qa:
    st.subheader("Data QA — API URL, Returned Columns, and Audit Table")

    if show_debug and not dbg.empty:
        st.markdown("### Request log (truth source)")
        st.dataframe(dbg, use_container_width=True, height=280)

    st.markdown("### Audit table")
    show = df.sort_values("ts", ascending=False)
    st.dataframe(show, use_container_width=True, height=360)

    csv = show.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", data=csv, file_name=f"caiso_{market_run_id.lower()}_{lookback_days}d_{location_key.split()[0].lower()}_lmp.csv", mime="text/csv")

st.markdown(f'<div class="footer">© {datetime.now().year} {COMPANY_NAME}. Internal use.</div>', unsafe_allow_html=True)
