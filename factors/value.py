"""
Factor 2 — Value (6 sub-factors)
Higher value = higher score (cheap is good for longs)
"""
import logging
import numpy as np
import pandas as pd

from factors.utils import pct_rank_within_sector, winsorize, safe_div

logger = logging.getLogger(__name__)


def compute_value(fundamentals: pd.DataFrame, sector_map: pd.Series) -> pd.DataFrame:
    """
    fundamentals: DataFrame indexed by ticker with fundamental columns
    Returns DataFrame with value sub-factors + value_score
    """
    tickers = [t for t in fundamentals.index if t in sector_map.index]
    if not tickers:
        return pd.DataFrame()

    f = fundamentals.loc[tickers].copy()
    sm = sector_map.loc[tickers]

    sub = pd.DataFrame(index=tickers)

    # Forward earnings yield (1 / forward P/E) — higher = cheaper
    sub["fwd_earnings_yield"] = safe_div(
        pd.Series(1.0, index=tickers),
        f.get("pe_ratio", pd.Series(np.nan, index=tickers))
    )

    # Book-to-price
    sub["book_to_price"] = safe_div(
        pd.Series(1.0, index=tickers),
        f.get("pb_ratio", pd.Series(np.nan, index=tickers))
    )

    # FCF yield (already computed in fundamentals)
    sub["fcf_yield"] = f.get("fcf_yield", pd.Series(np.nan, index=tickers))

    # EV/EBITDA inverted (lower EV/EBITDA = higher value score)
    sub["ev_ebitda_inv"] = safe_div(
        pd.Series(1.0, index=tickers),
        f.get("ev_ebitda", pd.Series(np.nan, index=tickers))
    )

    # Shareholder yield = buyback yield + dividend yield
    buy = f.get("buybacks", pd.Series(0.0, index=tickers)).fillna(0)
    div = f.get("dividends_paid", pd.Series(0.0, index=tickers)).fillna(0)
    mc = f.get("market_cap", pd.Series(np.nan, index=tickers))
    shareholder_yield = safe_div(buy + div, mc)
    sub["shareholder_yield"] = shareholder_yield

    # Sales-to-EV (revenue / EV) — works where P/E breaks
    rev = f.get("revenue", pd.Series(np.nan, index=tickers))
    ebitda = f.get("ebitda", pd.Series(np.nan, index=tickers))
    # Approximate EV ≈ market cap (simplified when EV not directly available)
    sub["sales_to_price"] = safe_div(rev, mc)

    # Score each sub-factor within sector
    scored = pd.DataFrame(index=tickers)
    for col in sub.columns:
        winsorized = winsorize(sub[col].dropna())
        sub.loc[winsorized.index, col] = winsorized
        scored[col] = pct_rank_within_sector(sub[col], sm)

    scored["value_score"] = scored.mean(axis=1)
    scored["value_score"] = pct_rank_within_sector(scored["value_score"], sm)
    return scored
