"""
Meridian Capital Partners — JARVIS Dashboard
L7: Streamlit Dashboard | Mobile-first | Dark Theme
"""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from datetime import datetime, timedelta
import sqlite3

from config import DB_PATH, AUM, CACHE_DIR, OUTPUT_DIR
CACHE_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ─── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Meridian Capital | JARVIS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── Theme CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
  --bg: #0b0e17;
  --card: linear-gradient(135deg, #131827 0%, #1a2035 100%);
  --accent: #6366f1;
  --long: #10b981;
  --short: #f43f5e;
  --text: #e2e8f0;
  --muted: #64748b;
  --border: #1e2740;
}

html, body, [class*="css"] {
  font-family: 'Plus Jakarta Sans', sans-serif !important;
  background-color: var(--bg) !important;
  color: var(--text) !important;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header { visibility: hidden; }
.stDeployButton { display: none; }
[data-testid="stToolbar"] { visibility: hidden; }
[data-testid="stSidebar"] > div:first-child { background: #0d1122; }

/* Main container */
.main .block-container {
  padding: 1rem 1rem 2rem 1rem;
  max-width: 1400px;
}

/* Card style */
.metric-card {
  background: linear-gradient(135deg, #131827 0%, #1a2035 100%);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
  margin: 4px 0;
}

/* Nav pills */
.nav-bar {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 20px;
  padding: 12px;
  background: #0d1122;
  border-radius: 12px;
  border: 1px solid var(--border);
}
.nav-pill {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.08em;
  padding: 6px 14px;
  border-radius: 20px;
  cursor: pointer;
  border: 1px solid var(--border);
  background: transparent;
  color: var(--muted);
  text-transform: uppercase;
}
.nav-pill.active {
  background: linear-gradient(135deg, #4f52c8, #6366f1);
  color: white;
  border-color: #6366f1;
  box-shadow: 0 0 12px rgba(99,102,241,0.3);
}

/* Metric display */
.big-metric { font-size: 28px; font-weight: 700; line-height: 1.1; }
.metric-label { font-size: 10px; text-transform: uppercase; letter-spacing: 0.1em; color: var(--muted); margin-bottom: 4px; }
.metric-change { font-size: 12px; font-family: 'JetBrains Mono', monospace; }
.pos { color: var(--long); }
.neg { color: var(--short); }
.neutral { color: var(--muted); }

/* Signal badges */
.badge-long { background: rgba(16,185,129,0.15); color: #10b981; border: 1px solid #10b981;
              padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge-short { background: rgba(244,63,94,0.15); color: #f43f5e; border: 1px solid #f43f5e;
               padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge-neutral { background: rgba(100,116,139,0.15); color: #64748b; border: 1px solid #64748b;
                 padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }

/* JARVIS header */
.jarvis-header {
  background: linear-gradient(135deg, #0d1122 0%, #131827 100%);
  border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 16px;
}
.jarvis-title { font-size: 28px; font-weight: 700; color: white; line-height: 1; }
.jarvis-sub { font-size: 10px; text-transform: uppercase; letter-spacing: 0.15em; color: var(--accent); }

/* Table styling */
[data-testid="stDataFrame"] {
  background: transparent !important;
  border-radius: 8px;
  overflow: hidden;
}

/* Streamlit metric override */
[data-testid="metric-container"] {
  background: linear-gradient(135deg, #131827 0%, #1a2035 100%);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 16px;
}
[data-testid="stMetricLabel"] { color: var(--muted) !important; font-size: 11px !important; text-transform: uppercase; letter-spacing: 0.08em; }
[data-testid="stMetricValue"] { color: var(--text) !important; font-family: 'JetBrains Mono', monospace !important; font-size: 22px !important; }
[data-testid="stMetricDelta"] { font-family: 'JetBrains Mono', monospace !important; }

/* Input fields */
.stTextInput input, .stNumberInput input, .stSelectbox select {
  background: #0d1122 !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
  border-radius: 8px !important;
}

/* Buttons */
.stButton button {
  background: linear-gradient(135deg, #4f52c8, #6366f1) !important;
  color: white !important;
  border: none !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  padding: 8px 20px !important;
}

/* Alert box */
.alert-high { background: rgba(244,63,94,0.1); border: 1px solid #f43f5e; border-radius: 8px; padding: 12px; margin: 4px 0; }
.alert-med { background: rgba(245,158,11,0.1); border: 1px solid #f59e0b; border-radius: 8px; padding: 12px; margin: 4px 0; }
.alert-low { background: rgba(99,102,241,0.1); border: 1px solid #6366f1; border-radius: 8px; padding: 12px; margin: 4px 0; }

/* Score bar */
.score-bar-bg { background: #1e2740; border-radius: 4px; height: 6px; width: 100%; }
.score-bar-fill { border-radius: 4px; height: 6px; }

/* Mobile tweaks */
@media (max-width: 768px) {
  .main .block-container { padding: 0.5rem; }
  .jarvis-title { font-size: 20px; }
  .big-metric { font-size: 22px; }
}
</style>
""", unsafe_allow_html=True)


# ─── Helpers ──────────────────────────────────────────────────────────────────
@st.cache_data(ttl=300)
def get_vix_data():
    try:
        vix = yf.Ticker("^VIX")
        info = vix.fast_info
        price = getattr(info, "last_price", None) or 20.0
        hist = vix.history(period="5d")
        prev = hist["Close"].iloc[-2] if len(hist) >= 2 else price
        return float(price), float(prev)
    except Exception:
        return 20.0, 20.0


@st.cache_data(ttl=300)
def get_market_snapshot():
    tickers = {"SPY": "S&P 500", "QQQ": "Nasdaq", "IWM": "Russell 2K", "^VIX": "VIX"}
    data = []
    for tk, name in tickers.items():
        try:
            t = yf.Ticker(tk)
            hist = t.history(period="2d")
            if len(hist) >= 2:
                close = hist["Close"].iloc[-1]
                prev = hist["Close"].iloc[-2]
                chg = (close - prev) / prev * 100
                data.append({"ticker": tk, "name": name, "price": close, "change_pct": chg})
        except Exception:
            pass
    return pd.DataFrame(data)


@st.cache_data(ttl=600)
def get_sector_performance():
    sectors = {
        "XLK": "Technology", "XLF": "Financials", "XLV": "Healthcare",
        "XLE": "Energy", "XLI": "Industrials", "XLC": "Comm Svcs",
        "XLY": "Cons Disc", "XLP": "Cons Staples", "XLB": "Materials",
        "XLRE": "Real Estate", "XLU": "Utilities"
    }
    data = []
    for tk, name in sectors.items():
        try:
            hist = yf.Ticker(tk).history(period="5d")
            if len(hist) >= 2:
                chg = (hist["Close"].iloc[-1] - hist["Close"].iloc[-2]) / hist["Close"].iloc[-2] * 100
                chg_1m = (hist["Close"].iloc[-1] - hist["Close"].iloc[0]) / hist["Close"].iloc[0] * 100
                data.append({"ticker": tk, "sector": name, "day_chg": chg, "week_chg": chg_1m})
        except Exception:
            pass
    return pd.DataFrame(data)


@st.cache_data(ttl=1800)
def get_scored_universe_cached():
    try:
        from factors.composite import get_scored_universe
        return get_scored_universe()
    except Exception:
        return pd.DataFrame()


def get_live_price(ticker: str) -> float | None:
    try:
        info = yf.Ticker(ticker).fast_info
        return getattr(info, "last_price", None)
    except Exception:
        return None


def score_color(score: float) -> str:
    if score >= 70:
        return "#10b981"
    elif score >= 50:
        return "#6366f1"
    elif score >= 30:
        return "#f59e0b"
    return "#f43f5e"


def regime_badge(vix: float) -> str:
    if vix < 15:
        return f'<span style="color:#10b981;font-family:monospace;font-size:12px">● LOW VOL (VIX {vix:.1f}) — Momentum regime</span>'
    elif vix > 25:
        return f'<span style="color:#f43f5e;font-family:monospace;font-size:12px">● HIGH VOL (VIX {vix:.1f}) — Quality/Value regime</span>'
    return f'<span style="color:#6366f1;font-family:monospace;font-size:12px">● NORMAL (VIX {vix:.1f}) — Balanced regime</span>'


# ─── Navigation ───────────────────────────────────────────────────────────────
PAGES = ["I  PORTFOLIO", "II  SCREENER", "III  RISK", "IV  MARKET", "V  ADD TRADE"]

if "page" not in st.session_state:
    st.session_state.page = PAGES[0]

# Header
vix_now, vix_prev = get_vix_data()
vix_chg = vix_now - vix_prev

st.markdown(f"""
<div class="jarvis-header">
  <div>
    <div class="jarvis-sub">Meridian Capital Partners</div>
    <div class="jarvis-title">⚡ JARVIS</div>
    <div style="font-size:12px;color:#64748b;margin-top:4px;font-family:'JetBrains Mono',monospace">
      LONG/SHORT EQUITY ANALYST
    </div>
  </div>
  <div style="margin-left:auto;text-align:right">
    <div style="font-size:10px;color:#64748b;text-transform:uppercase;letter-spacing:0.1em">Market Status</div>
    <div style="margin-top:4px">{regime_badge(vix_now)}</div>
    <div style="font-size:10px;color:#64748b;margin-top:4px">{datetime.now().strftime("%a %b %d, %Y  %H:%M")}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# Nav bar
cols = st.columns(len(PAGES))
for i, (col, pg) in enumerate(zip(cols, PAGES)):
    with col:
        active = "active" if st.session_state.page == pg else ""
        if st.button(pg, key=f"nav_{i}", use_container_width=True):
            st.session_state.page = pg
            st.rerun()

page = st.session_state.page


# ══════════════════════════════════════════════════════════════════════════════
# PAGE I — PORTFOLIO
# ══════════════════════════════════════════════════════════════════════════════
if "PORTFOLIO" in page:
    from portfolio.state import (
        get_open_positions, get_portfolio_summary, get_realized_trades,
        position_size_recommendation, close_position, _init_db
    )
    _init_db()

    summary = get_portfolio_summary(AUM)
    positions = get_open_positions()
    realized = get_realized_trades()

    # KPI row
    st.markdown("### Portfolio Overview")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Account Value", f"${summary['current_value']:.2f}",
              f"{summary['total_return_pct']:+.1f}%")
    c2.metric("Total P&L", f"${summary['total_pnl']:.2f}",
              f"${summary['unrealized_pnl']:.2f} unrealized")
    c3.metric("Positions", f"{summary['num_longs']}L / {summary['num_shorts']}S")
    c4.metric("Cash", f"${summary['cash']:.2f}",
              f"{summary['cash']/AUM*100:.0f}% of AUM")
    c5.metric("Gross Exposure", f"${summary['gross_exposure']:.2f}",
              f"Net ${summary['net_exposure']:.2f}")

    st.divider()

    if not positions.empty:
        st.markdown("### Open Positions")

        # Colour-code P&L
        def style_pnl(val):
            color = "#10b981" if val > 0 else "#f43f5e" if val < 0 else "#64748b"
            return f"color: {color}; font-family: 'JetBrains Mono', monospace"

        display = positions[[
            "id", "ticker", "side", "shares", "entry_price",
            "current_price", "market_value", "unrealized_pnl", "unrealized_pnl_pct",
            "sector", "entry_date"
        ]].copy()
        display["unrealized_pnl_pct"] = display["unrealized_pnl_pct"].apply(
            lambda x: f"{x*100:.1f}%" if pd.notna(x) else "—"
        )
        display["unrealized_pnl"] = display["unrealized_pnl"].apply(
            lambda x: f"${x:.2f}" if pd.notna(x) else "—"
        )
        display["market_value"] = display["market_value"].apply(
            lambda x: f"${x:.2f}" if pd.notna(x) else "—"
        )
        display["entry_price"] = display["entry_price"].apply(lambda x: f"${x:.2f}")
        display["current_price"] = display["current_price"].apply(
            lambda x: f"${x:.2f}" if pd.notna(x) else "—"
        )

        st.dataframe(
            display.rename(columns={
                "id": "ID", "ticker": "Ticker", "side": "Side",
                "shares": "Shares", "entry_price": "Entry",
                "current_price": "Current", "market_value": "Value",
                "unrealized_pnl": "P&L", "unrealized_pnl_pct": "P&L %",
                "sector": "Sector", "entry_date": "Date"
            }),
            use_container_width=True, hide_index=True
        )

        # Close position widget
        with st.expander("📤 Close a Position"):
            col1, col2, col3 = st.columns(3)
            with col1:
                pos_id = st.number_input("Position ID", min_value=1, step=1)
            with col2:
                close_px = st.number_input("Exit Price ($)", min_value=0.01, step=0.01)
            with col3:
                st.write("")
                st.write("")
                if st.button("Close Position"):
                    close_position(int(pos_id), float(close_px))
                    st.success(f"Position {pos_id} closed at ${close_px:.2f}")
                    st.rerun()
    else:
        st.info("No open positions. Use **V ADD TRADE** to log your first trade.")

    # Realized trades
    if not realized.empty:
        st.divider()
        st.markdown("### Realized Trades")
        wl = realized.copy()
        wl["pnl"] = wl["pnl"].apply(lambda x: f"${x:.2f}")
        wl["pnl_pct"] = wl["pnl_pct"].apply(lambda x: f"{x*100:.1f}%")
        st.dataframe(wl[["ticker", "side", "shares", "entry_price", "exit_price",
                          "entry_date", "exit_date", "pnl", "pnl_pct", "holding_days"]],
                     use_container_width=True, hide_index=True)

        # Win rate stats
        r = realized.copy()
        wins = (r["pnl"] > 0).sum()
        losses = (r["pnl"] <= 0).sum()
        total = len(r)
        avg_win = r[r["pnl"] > 0]["pnl"].mean() if wins > 0 else 0
        avg_loss = r[r["pnl"] <= 0]["pnl"].mean() if losses > 0 else 0

        w1, w2, w3, w4 = st.columns(4)
        w1.metric("Win Rate", f"{wins/total*100:.0f}%" if total > 0 else "—")
        w2.metric("Total Trades", total)
        w3.metric("Avg Win", f"${avg_win:.2f}")
        w4.metric("Avg Loss", f"${avg_loss:.2f}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE II — SCREENER
# ══════════════════════════════════════════════════════════════════════════════
elif "SCREENER" in page:
    st.markdown("### Stock Screener")

    col_a, col_b = st.columns([3, 1])
    with col_b:
        if st.button("🔄 Refresh Scores", use_container_width=True):
            with st.spinner("Running scoring engine… (this takes a few minutes on first run)"):
                try:
                    from data.universe import get_universe
                    from data.market_data import fetch_prices, fetch_fundamentals
                    from data.short_interest import fetch_short_interest
                    from factors.composite import run_scoring

                    df_uni = get_universe()
                    tickers = df_uni["ticker"].head(30).tolist()  # 30 for speed on free plan

                    fetch_prices(tickers)
                    fetch_fundamentals(tickers)
                    fetch_short_interest(tickers)
                    result = run_scoring(tickers)
                    st.cache_data.clear()
                    st.success(f"Scored {len(result)} tickers!")
                except Exception as e:
                    st.error(f"Scoring error: {e}")
            st.rerun()

    scored = get_scored_universe_cached()

    if scored.empty:
        st.warning("""
        **No scored data yet.** Click **🔄 Refresh Scores** to run the scoring engine.

        First run fetches data for ~30 S&P 500 stocks — takes 2-3 minutes.
        """)
        st.info("""
        **While you wait, here's what the screener does:**
        - Scores S&P 500 stocks on 8 factors (momentum, quality, value, growth, insider activity, short interest, estimate revisions, institutional flow)
        - Ranks each factor within GICS sector (0-100 percentile)
        - Blends into a composite score with regime-conditional weights
        - Flags top quintile as **LONG** candidates, bottom quintile as **SHORT** candidates
        """)
    else:
        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            signal_filter = st.selectbox("Signal", ["ALL", "LONG", "SHORT", "NEUTRAL"])
        with col2:
            sectors = ["ALL"] + sorted(scored["sector"].dropna().unique().tolist()) if "sector" in scored.columns else ["ALL"]
            sector_filter = st.selectbox("Sector", sectors)
        with col3:
            sort_by = st.selectbox("Sort by", ["composite_score", "momentum_score", "quality_score", "value_score"])

        df_show = scored.copy().reset_index()
        if "ticker" not in df_show.columns and scored.index.name == "ticker":
            df_show = df_show.rename(columns={"index": "ticker"})

        if signal_filter != "ALL" and "signal" in df_show.columns:
            df_show = df_show[df_show["signal"] == signal_filter]
        if sector_filter != "ALL" and "sector" in df_show.columns:
            df_show = df_show[df_show["sector"] == sector_filter]

        if sort_by in df_show.columns:
            df_show = df_show.sort_values(sort_by, ascending=(signal_filter == "SHORT"))

        score_cols = [c for c in ["composite_score", "momentum_score", "quality_score",
                                   "value_score", "growth_score", "insider_score"] if c in df_show.columns]
        show_cols = ["ticker"] + (["name"] if "name" in df_show.columns else []) + \
                    (["sector"] if "sector" in df_show.columns else []) + \
                    score_cols + (["signal"] if "signal" in df_show.columns else [])

        display = df_show[show_cols].head(50).copy()
        for c in score_cols:
            display[c] = display[c].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "—")

        st.dataframe(display, use_container_width=True, hide_index=True)

        # Top candidates summary
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### 🟢 Top Long Candidates")
            if "signal" in df_show.columns:
                top_longs = scored[scored.get("signal", pd.Series()) == "LONG"].nlargest(10, "composite_score") if "signal" in scored.columns else pd.DataFrame()
                if not top_longs.empty:
                    for tk, row in top_longs.head(5).iterrows():
                        score = row.get("composite_score", 50)
                        name = row.get("name", tk)
                        sector = row.get("sector", "")
                        st.markdown(f"""
                        <div class="metric-card" style="margin:4px 0">
                          <div style="display:flex;justify-content:space-between;align-items:center">
                            <div>
                              <div style="font-weight:700;color:white">{tk}</div>
                              <div style="font-size:11px;color:#64748b">{name[:25] if name else ''} · {sector}</div>
                            </div>
                            <div style="text-align:right">
                              <div style="font-size:20px;font-weight:700;color:{score_color(score)};font-family:'JetBrains Mono',monospace">{score:.0f}</div>
                              <span class="badge-long">LONG</span>
                            </div>
                          </div>
                        </div>
                        """, unsafe_allow_html=True)

        with c2:
            st.markdown("#### 🔴 Top Short Candidates")
            if "signal" in scored.columns:
                top_shorts = scored[scored["signal"] == "SHORT"].nsmallest(10, "composite_score")
                if not top_shorts.empty:
                    for tk, row in top_shorts.head(5).iterrows():
                        score = row.get("composite_score", 50)
                        name = row.get("name", tk)
                        sector = row.get("sector", "")
                        st.markdown(f"""
                        <div class="metric-card" style="margin:4px 0">
                          <div style="display:flex;justify-content:space-between;align-items:center">
                            <div>
                              <div style="font-weight:700;color:white">{tk}</div>
                              <div style="font-size:11px;color:#64748b">{name[:25] if name else ''} · {sector}</div>
                            </div>
                            <div style="text-align:right">
                              <div style="font-size:20px;font-weight:700;color:{score_color(score)};font-family:'JetBrains Mono',monospace">{score:.0f}</div>
                              <span class="badge-short">SHORT</span>
                            </div>
                          </div>
                        </div>
                        """, unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE III — RISK
# ══════════════════════════════════════════════════════════════════════════════
elif "RISK" in page:
    from portfolio.state import get_open_positions, get_portfolio_summary, _init_db
    _init_db()

    st.markdown("### Risk Dashboard")

    summary = get_portfolio_summary(AUM)
    positions = get_open_positions()

    # Circuit breakers
    vix_now, vix_prev = get_vix_data()
    daily_return = 0.0  # Would come from real P&L tracking
    drawdown = (summary["current_value"] - AUM) / AUM  # simplified

    st.markdown("#### Circuit Breakers")
    cb1, cb2, cb3 = st.columns(3)
    with cb1:
        daily_loss_pct = abs(min(daily_return, 0)) * 100
        status = "🟢 OK" if daily_loss_pct < 1.5 else ("🟡 SIZE DOWN" if daily_loss_pct < 2.5 else "🔴 CLOSE ALL")
        st.metric("Daily Loss", f"{daily_loss_pct:.2f}%", f"Limit: 1.5% / 2.5%")
        st.caption(status)
    with cb2:
        dd_pct = abs(min(drawdown, 0)) * 100
        status = "🟢 OK" if dd_pct < 4 else ("🟡 SIZE DOWN" if dd_pct < 8 else "🔴 KILL SWITCH")
        st.metric("Max Drawdown", f"{dd_pct:.2f}%", f"Limit: 4% / 8%")
        st.caption(status)
    with cb3:
        st.metric("VIX", f"{vix_now:.1f}", f"{vix_chg:+.1f} vs yesterday")
        status = "🟢 Normal" if vix_now < 25 else "🔴 REDUCE 50%"
        st.caption(status)

    st.divider()

    # Position limits for $200
    st.markdown("#### Position Sizing Guide ($200 AUM)")
    sizing_data = [
        {"Max per position (10%)": "$20", "Target positions (long)": "10",
         "Target positions (short)": "5", "Max sector (30%)": "$60"},
    ]
    st.markdown("""
    <div class="metric-card">
    <table style="width:100%;border-collapse:collapse">
    <tr style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:0.08em">
      <td>Max Per Position</td><td>Long Target</td><td>Short Target</td><td>Max Sector</td><td>Gross Limit</td>
    </tr>
    <tr style="font-family:'JetBrains Mono',monospace;font-size:16px;color:white">
      <td style="color:#10b981">$20 (10%)</td>
      <td>10 stocks</td>
      <td>5 stocks</td>
      <td style="color:#f59e0b">$60 (30%)</td>
      <td>$300 (150%)</td>
    </tr>
    </table>
    </div>
    """, unsafe_allow_html=True)

    # Tail risk alerts
    st.divider()
    st.markdown("#### Tail Risk Alerts")

    alerts = []
    if vix_now >= 35:
        alerts.append(("HIGH", "🚨 VIX ≥ 35 — REDUCE GROSS EXPOSURE 50%"))
    elif vix_now >= 25:
        alerts.append(("MED", "⚠️ VIX ≥ 25 — REDUCE GROSS EXPOSURE 20%"))

    if summary["gross_exposure"] > AUM * 1.65:
        alerts.append(("HIGH", f"🚨 Gross exposure ${summary['gross_exposure']:.0f} exceeds 165% limit"))

    if summary["num_longs"] > 10:
        alerts.append(("MED", f"⚠️ {summary['num_longs']} long positions exceeds target of 10"))

    if not positions.empty:
        for _, row in positions.iterrows():
            if pd.notna(row.get("market_value")) and row["market_value"] > AUM * 0.10:
                alerts.append(("HIGH", f"🚨 {row['ticker']}: position ${row['market_value']:.0f} exceeds 10% AUM limit"))

    if not alerts:
        alerts.append(("LOW", "✅ All risk checks passing"))

    for level, msg in alerts:
        css = {"HIGH": "alert-high", "MED": "alert-med", "LOW": "alert-low"}.get(level, "alert-low")
        st.markdown(f'<div class="{css}">{msg}</div>', unsafe_allow_html=True)

    # Pre-trade checklist
    st.divider()
    st.markdown("#### Pre-Trade Checklist (8 Checks)")
    st.markdown("""
    Before entering any trade, verify:

    1. ✅ No trading halt on ticker
    2. ✅ Not within 5 days of earnings (halve size if so)
    3. ✅ Liquidity — position ≤ 5% of 20-day ADV
    4. ✅ Position ≤ 10% of $200 AUM (max $20)
    5. ✅ Sector allocation ≤ 30% ($60 max)
    6. ✅ Gross exposure ≤ 150% ($300 max)
    7. ✅ Net beta exposure ≤ 20%
    8. ✅ Correlation ≤ 0.80 with existing positions
    """)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE IV — MARKET OVERVIEW
# ══════════════════════════════════════════════════════════════════════════════
elif "MARKET" in page:
    st.markdown("### Market Overview")

    # Index performance
    snap = get_market_snapshot()
    if not snap.empty:
        cols = st.columns(len(snap))
        for col, (_, row) in zip(cols, snap.iterrows()):
            chg = row["change_pct"]
            color = "#10b981" if chg > 0 else "#f43f5e"
            col.markdown(f"""
            <div class="metric-card" style="text-align:center">
              <div class="metric-label">{row['name']}</div>
              <div class="big-metric">{row['price']:.1f if row['ticker'] == '^VIX' else f"{row['price']:.0f}"}</div>
              <div class="metric-change" style="color:{color}">{chg:+.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
    st.divider()

    # Sector heatmap
    st.markdown("#### Sector Performance")
    sectors = get_sector_performance()
    if not sectors.empty:
        fig = go.Figure(go.Bar(
            x=sectors["day_chg"],
            y=sectors["sector"],
            orientation="h",
            marker_color=["#10b981" if x > 0 else "#f43f5e" for x in sectors["day_chg"]],
            text=[f"{x:+.2f}%" for x in sectors["day_chg"]],
            textposition="auto",
        ))
        fig.update_layout(
            plot_bgcolor="#0b0e17",
            paper_bgcolor="#0b0e17",
            font_color="#e2e8f0",
            font_family="JetBrains Mono",
            height=400,
            margin=dict(l=0, r=0, t=20, b=0),
            xaxis=dict(gridcolor="#1e2740", zerolinecolor="#64748b", tickformat=".1f"),
            yaxis=dict(gridcolor="#1e2740"),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # Price chart for any ticker
    st.markdown("#### Price Chart")
    col1, col2 = st.columns([2, 1])
    with col1:
        chart_ticker = st.text_input("Ticker", value="SPY", placeholder="e.g. AAPL")
    with col2:
        period = st.selectbox("Period", ["1mo", "3mo", "6mo", "1y", "2y"], index=1)

    if chart_ticker:
        try:
            hist = yf.Ticker(chart_ticker.upper()).history(period=period)
            if not hist.empty:
                fig2 = go.Figure()
                fig2.add_trace(go.Candlestick(
                    x=hist.index,
                    open=hist["Open"], high=hist["High"],
                    low=hist["Low"], close=hist["Close"],
                    increasing_line_color="#10b981",
                    decreasing_line_color="#f43f5e",
                    name=chart_ticker.upper()
                ))
                # 50-day MA
                hist["MA50"] = hist["Close"].rolling(50).mean()
                fig2.add_trace(go.Scatter(
                    x=hist.index, y=hist["MA50"],
                    line=dict(color="#6366f1", width=1.5),
                    name="50 MA"
                ))
                fig2.update_layout(
                    plot_bgcolor="#0b0e17", paper_bgcolor="#0b0e17",
                    font_color="#e2e8f0", font_family="JetBrains Mono",
                    height=420,
                    margin=dict(l=0, r=0, t=20, b=0),
                    xaxis=dict(gridcolor="#1e2740", rangeslider_visible=False),
                    yaxis=dict(gridcolor="#1e2740"),
                    legend=dict(bgcolor="#0d1122", bordercolor="#1e2740"),
                )
                st.plotly_chart(fig2, use_container_width=True)
        except Exception as e:
            st.error(f"Chart error: {e}")

    # Quick lookup
    st.divider()
    st.markdown("#### Quick Fundamentals Lookup")
    lookup = st.text_input("Ticker for fundamentals", placeholder="e.g. NVDA")
    if lookup:
        try:
            info = yf.Ticker(lookup.upper()).info
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("Market Cap", f"${info.get('marketCap', 0)/1e9:.1f}B" if info.get('marketCap') else "—")
            f2.metric("P/E (TTM)", f"{info.get('trailingPE', 0):.1f}" if info.get('trailingPE') else "—")
            f3.metric("P/B", f"{info.get('priceToBook', 0):.1f}" if info.get('priceToBook') else "—")
            f4.metric("Beta", f"{info.get('beta', 0):.2f}" if info.get('beta') else "—")

            g1, g2, g3, g4 = st.columns(4)
            g1.metric("Revenue Growth", f"{info.get('revenueGrowth', 0)*100:.1f}%" if info.get('revenueGrowth') else "—")
            g2.metric("Gross Margin", f"{info.get('grossMargins', 0)*100:.1f}%" if info.get('grossMargins') else "—")
            g3.metric("ROE", f"{info.get('returnOnEquity', 0)*100:.1f}%" if info.get('returnOnEquity') else "—")
            g4.metric("Short Float %", f"{info.get('shortPercentOfFloat', 0)*100:.1f}%" if info.get('shortPercentOfFloat') else "—")
        except Exception as e:
            st.error(f"Lookup error: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PAGE V — ADD TRADE
# ══════════════════════════════════════════════════════════════════════════════
elif "ADD TRADE" in page:
    from portfolio.state import (
        add_position, position_size_recommendation, _init_db
    )
    _init_db()

    st.markdown("### Log a Manual Trade")
    st.info("Enter the details of a trade you've placed through your broker. The dashboard will track P&L automatically.")

    with st.form("add_trade_form"):
        col1, col2 = st.columns(2)
        with col1:
            ticker = st.text_input("Ticker Symbol", placeholder="e.g. AAPL").upper()
            side = st.selectbox("Direction", ["LONG", "SHORT"])
            sector = st.text_input("Sector (optional)", placeholder="Technology")
        with col2:
            entry_price = st.number_input("Entry Price ($)", min_value=0.01, step=0.01, value=1.00)
            shares = st.number_input("Number of Shares", min_value=0.0001, step=0.0001, value=1.0)
            notes = st.text_input("Notes (optional)", placeholder="Why this trade?")

        submitted = st.form_submit_button("📥 Log Trade", use_container_width=True)

        if submitted and ticker and entry_price > 0 and shares > 0:
            pid = add_position(
                ticker=ticker, side=side, shares=shares,
                entry_price=entry_price, sector=sector, notes=notes
            )
            st.success(f"✅ Trade logged! Position ID: {pid}")
            st.markdown(f"**{side} {shares:.4f} shares of {ticker} @ ${entry_price:.2f}** → Total: ${entry_price*shares:.2f}")

    # Position sizing tool
    st.divider()
    st.markdown("### Position Size Calculator")
    st.markdown(f"*Based on ${AUM:.0f} AUM — adjust in config.py*")

    ps1, ps2, ps3 = st.columns(3)
    with ps1:
        calc_ticker = st.text_input("Ticker", value="", placeholder="e.g. TSLA", key="calc_tk")
    with ps2:
        calc_price = st.number_input("Stock Price ($)", min_value=0.01, step=0.01, value=100.0, key="calc_px")
    with ps3:
        calc_score = st.slider("Conviction Score (0-100)", 0, 100, 65, key="calc_score")

    if st.button("Calculate Size", key="calc_btn"):
        live = get_live_price(calc_ticker) if calc_ticker else None
        price = live or calc_price
        rec = position_size_recommendation(price, AUM, calc_score)

        st.markdown(f"""
        <div class="metric-card">
          <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;text-align:center">
            <div>
              <div class="metric-label">Recommended $</div>
              <div class="big-metric" style="color:#10b981">${rec['dollar_amount']:.2f}</div>
            </div>
            <div>
              <div class="metric-label">Shares</div>
              <div class="big-metric">{rec['shares']}</div>
            </div>
            <div>
              <div class="metric-label">% of AUM</div>
              <div class="big-metric">{rec['recommended_pct']:.1f}%</div>
            </div>
            <div>
              <div class="metric-label">Actual Cost</div>
              <div class="big-metric" style="color:#6366f1">${rec['actual_dollar']:.2f}</div>
            </div>
          </div>
          <div style="margin-top:12px;font-size:11px;color:#64748b">
            Based on conviction score {calc_score}/100 · Price ${price:.2f} · Max position ${ AUM * 0.10:.0f}
          </div>
        </div>
        """, unsafe_allow_html=True)

        if live:
            st.caption(f"📡 Live price fetched: ${live:.2f}")

    # Earnings check
    st.divider()
    st.markdown("### Earnings Dates Check")
    earn_ticker = st.text_input("Check earnings for:", placeholder="e.g. MSFT", key="earn_tk")
    if earn_ticker:
        try:
            cal = yf.Ticker(earn_ticker.upper()).calendar
            if cal is not None and not (isinstance(cal, pd.DataFrame) and cal.empty):
                if isinstance(cal, pd.DataFrame):
                    st.dataframe(cal, use_container_width=True)
                else:
                    st.json(cal)
            else:
                st.info("No upcoming earnings data found.")
        except Exception as e:
            st.warning(f"Could not fetch earnings calendar: {e}")
