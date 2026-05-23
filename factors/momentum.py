"""
Factor 1 — Momentum (6 sub-factors, sector-relative percentile rank 0-100)
"""
import logging
import numpy as np
import pandas as pd

from factors.utils import pct_rank_within_sector, winsorize

logger = logging.getLogger(__name__)


def compute_momentum(prices: pd.DataFrame, sector_map: pd.Series) -> pd.DataFrame:
    """
    prices: close-price pivot (dates × tickers)
    sector_map: Series(ticker → sector)
    Returns DataFrame with columns: [sub-factors..., momentum_score]
    """
    tickers = [c for c in prices.columns if c in sector_map.index]
    if not tickers:
        return pd.DataFrame()

    px = prices[tickers].ffill()
    today = px.iloc[-1]

    def ret(days: int) -> pd.Series:
        if len(px) < days + 1:
            return pd.Series(np.nan, index=tickers)
        return (today / px.iloc[-(days + 1)] - 1).replace([np.inf, -np.inf], np.nan)

    # 12-1 month (skip last month to avoid short-term reversal)
    r12 = ret(252)
    r1 = ret(21)
    mom_12_1 = (r12 - r1).rename("mom_12_1")

    # 6-month return
    mom_6 = ret(126).rename("mom_6")

    # 3-month return
    mom_3 = ret(63).rename("mom_3")

    # Acceleration: recent 3m minus older 3m
    r6 = ret(126)
    r3 = ret(63)
    acceleration = (r3 - (r6 - r3)).rename("acceleration")

    # 52-week-high proximity (George & Hwang 2004)
    high_52w = px.tail(252).max()
    proximity_52w = (today / high_52w).rename("proximity_52w")

    # Relative strength vs sector ETF
    # We'll compute this vs SPY as a proxy when sector ETF data is unavailable
    if "SPY" in prices.columns:
        spy_r6 = (prices["SPY"].iloc[-1] / prices["SPY"].iloc[-127] - 1) if len(prices) > 127 else np.nan
        rs_sector = (r6 - spy_r6).rename("rs_sector")
    else:
        rs_sector = r6.rename("rs_sector")

    # Combine sub-factors into a DataFrame
    sub = pd.concat([mom_12_1, mom_6, mom_3, acceleration, proximity_52w, rs_sector], axis=1)
    sub = sub.loc[tickers]

    # Rank each sub-factor within sector
    scored = pd.DataFrame(index=tickers)
    sm = sector_map.loc[tickers]
    for col in sub.columns:
        raw = winsorize(sub[col].dropna())
        sub.loc[raw.index, col] = raw
        scored[col] = pct_rank_within_sector(sub[col], sm)

    scored["momentum_score"] = scored.mean(axis=1)
    scored["momentum_score"] = pct_rank_within_sector(scored["momentum_score"], sm)
    return scored
