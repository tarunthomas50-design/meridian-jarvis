"""
Layer 2 — Composite Score: weighted blend of all factor scores → sector re-rank → LONG/SHORT flag.
Saves scored_universe_latest.csv to output/.
"""
import logging
import sqlite3
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import (
    DB_PATH, OUTPUT_DIR, FACTOR_WEIGHTS, REGIME_WEIGHTS,
    VIX_LOW, VIX_HIGH
)
from data.universe import get_universe
from data.market_data import get_prices_multi, get_fundamentals
from data.short_interest import get_short_interest
from factors.momentum import compute_momentum
from factors.value import compute_value
from factors.quality import compute_quality
from factors.growth import compute_growth
from factors.insider import compute_insider
from factors.short_interest_factor import compute_short_interest
from factors.utils import pct_rank_within_sector

logger = logging.getLogger(__name__)


def get_vix_regime() -> str:
    try:
        vix = yf.Ticker("^VIX").info.get("regularMarketPrice") or \
              yf.download("^VIX", period="1d", progress=False)["Close"].iloc[-1]
        vix = float(vix)
        if vix < VIX_LOW:
            return "low_vol"
        elif vix > VIX_HIGH:
            return "high_vol"
        return "normal"
    except Exception:
        return "normal"


def run_scoring(tickers: list[str] | None = None, regime: str | None = None) -> pd.DataFrame:
    """
    Run the full scoring pipeline.
    Returns DataFrame indexed by ticker with all factor scores + composite + LONG/SHORT flag.
    """
    universe = get_universe()
    if universe.empty:
        logger.error("Universe is empty — run data refresh first")
        return pd.DataFrame()

    if tickers:
        universe = universe[universe["ticker"].isin(tickers)]

    sector_map = universe.set_index("ticker")["sector"]

    # Get prices (for momentum)
    all_tickers = universe["ticker"].tolist()
    prices = get_prices_multi(all_tickers + ["SPY"], days=400)

    if prices.empty:
        logger.warning("No price data in DB — composite will use fundamentals only")

    # Get fundamentals
    fundamentals = get_fundamentals(all_tickers)
    if not fundamentals.empty:
        fundamentals = fundamentals.set_index("ticker")
    else:
        fundamentals = pd.DataFrame(index=all_tickers)

    # Get short interest
    si_raw = get_short_interest(all_tickers)
    if not si_raw.empty:
        si_raw = si_raw.set_index("ticker")
    else:
        si_raw = pd.DataFrame(index=all_tickers)

    # Compute each factor
    results = {}

    if not prices.empty:
        mom = compute_momentum(prices, sector_map)
        results["momentum"] = mom["momentum_score"] if not mom.empty else pd.Series(50.0, index=all_tickers)
    else:
        results["momentum"] = pd.Series(50.0, index=all_tickers)

    if not fundamentals.empty:
        val = compute_value(fundamentals, sector_map)
        qua = compute_quality(fundamentals, sector_map)
        gro = compute_growth(fundamentals, sector_map)
        results["value"] = val["value_score"] if not val.empty else pd.Series(50.0, index=all_tickers)
        results["quality"] = qua["quality_score"] if not qua.empty else pd.Series(50.0, index=all_tickers)
        results["growth"] = gro["growth_score"] if not gro.empty else pd.Series(50.0, index=all_tickers)
    else:
        for f in ["value", "quality", "growth"]:
            results[f] = pd.Series(50.0, index=all_tickers)

    ins = compute_insider(all_tickers, sector_map)
    results["insider"] = ins["insider_score"] if not ins.empty else pd.Series(50.0, index=all_tickers)

    if not si_raw.empty:
        si_f = compute_short_interest(si_raw, sector_map, for_longs=True)
        results["short_interest"] = si_f["short_interest_score"] if not si_f.empty else pd.Series(50.0, index=all_tickers)
    else:
        results["short_interest"] = pd.Series(50.0, index=all_tickers)

    # Estimate revisions (neutral 50 until 30 days of snapshots available)
    results["revisions"] = pd.Series(50.0, index=all_tickers)
    # Institutional (neutral until 13F data populated)
    results["institutional"] = pd.Series(50.0, index=all_tickers)

    # Regime-conditional weights
    if regime is None:
        regime = get_vix_regime()
    weights = REGIME_WEIGHTS.get(regime, FACTOR_WEIGHTS)

    # Build composite
    factor_df = pd.DataFrame(results).reindex(all_tickers)
    composite = pd.Series(0.0, index=all_tickers)
    for factor, w in weights.items():
        if factor in factor_df.columns:
            composite += factor_df[factor].fillna(50.0) * w

    factor_df["composite_raw"] = composite

    # Re-rank composite within sector
    factor_df["composite_score"] = pct_rank_within_sector(factor_df["composite_raw"], sector_map)

    # Add universe metadata
    factor_df = factor_df.join(universe.set_index("ticker")[["name", "sector", "sub_industry"]])

    # LONG/SHORT flag: top quintile = LONG, bottom quintile = SHORT
    factor_df["signal"] = "NEUTRAL"
    factor_df.loc[factor_df["composite_score"] >= 80, "signal"] = "LONG"
    factor_df.loc[factor_df["composite_score"] <= 20, "signal"] = "SHORT"

    factor_df["regime"] = regime
    factor_df["scored_at"] = datetime.now().isoformat()

    # Save
    out_path = OUTPUT_DIR / "scored_universe_latest.csv"
    factor_df.to_csv(out_path)
    logger.info(f"Scored {len(factor_df)} tickers → {out_path}")

    # Cache in DB
    try:
        conn = sqlite3.connect(DB_PATH)
        factor_df.reset_index().rename(columns={"index": "ticker"}).to_sql(
            "scored_universe", conn, if_exists="replace", index=False
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning(f"DB cache failed: {e}")

    return factor_df


def get_scored_universe() -> pd.DataFrame:
    """Load latest scored universe from DB or CSV."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT * FROM scored_universe", conn)
        conn.close()
        if not df.empty:
            return df.set_index("ticker")
    except Exception:
        pass

    csv = OUTPUT_DIR / "scored_universe_latest.csv"
    if csv.exists():
        return pd.read_csv(csv, index_col=0)

    return pd.DataFrame()


def get_top_candidates(n: int = 10) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return top N longs and top N shorts from scored universe."""
    df = get_scored_universe()
    if df.empty:
        return pd.DataFrame(), pd.DataFrame()
    longs = df[df["signal"] == "LONG"].nlargest(n, "composite_score")
    shorts = df[df["signal"] == "SHORT"].nsmallest(n, "composite_score")
    return longs, shorts


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = run_scoring()
    print(f"\nTop 5 LONGS:\n{df[df['signal']=='LONG'].nlargest(5,'composite_score')[['name','sector','composite_score']]}")
    print(f"\nTop 5 SHORTS:\n{df[df['signal']=='SHORT'].nsmallest(5,'composite_score')[['name','sector','composite_score']]}")
