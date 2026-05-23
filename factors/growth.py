"""
Factor 4 — Growth (5 sub-factors)
"""
import numpy as np
import pandas as pd

from factors.utils import pct_rank_within_sector, winsorize, safe_div


def compute_growth(fundamentals: pd.DataFrame, sector_map: pd.Series) -> pd.DataFrame:
    tickers = [t for t in fundamentals.index if t in sector_map.index]
    if not tickers:
        return pd.DataFrame()

    f = fundamentals.loc[tickers].copy()
    sm = sector_map.loc[tickers]
    sub = pd.DataFrame(index=tickers)

    sub["revenue_growth_yoy"] = f.get("revenue_growth_yoy", pd.Series(np.nan, index=tickers))
    sub["earnings_growth_yoy"] = f.get("earnings_growth_yoy", pd.Series(np.nan, index=tickers))

    # Revenue growth acceleration (need two periods — use 0 as neutral if unavailable)
    sub["revenue_accel"] = pd.Series(0.0, index=tickers)  # placeholder

    # R&D intensity (R&D / Revenue — high = innovation)
    rd = f.get("rd_expense", pd.Series(np.nan, index=tickers))
    rev = f.get("revenue", pd.Series(np.nan, index=tickers))
    sub["rd_intensity"] = safe_div(rd.abs(), rev.abs())

    # FCF yield as growth proxy (FCF reinvestment capacity)
    sub["fcf_yield"] = f.get("fcf_yield", pd.Series(np.nan, index=tickers))

    scored = pd.DataFrame(index=tickers)
    for col in sub.columns:
        w = winsorize(sub[col].dropna())
        sub.loc[w.index, col] = w
        scored[col] = pct_rank_within_sector(sub[col], sm)

    scored["growth_score"] = scored.mean(axis=1)
    scored["growth_score"] = pct_rank_within_sector(scored["growth_score"], sm)
    return scored
