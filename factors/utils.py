"""
Shared utilities for factor computation.
"""
import numpy as np
import pandas as pd


def pct_rank_within_sector(series: pd.Series, sector_map: pd.Series) -> pd.Series:
    """
    Rank each value 0-100 within its GICS sector.
    series: values indexed by ticker
    sector_map: sector indexed by ticker
    """
    result = pd.Series(index=series.index, dtype=float)
    for sector in sector_map.unique():
        mask = sector_map == sector
        tickers = mask[mask].index
        sub = series[tickers].dropna()
        if len(sub) < 2:
            result[tickers] = 50.0
            continue
        ranked = sub.rank(pct=True) * 100
        result[sub.index] = ranked
    result = result.fillna(50.0)
    return result


def winsorize(s: pd.Series, pct: float = 0.01) -> pd.Series:
    lo = s.quantile(pct)
    hi = s.quantile(1 - pct)
    return s.clip(lo, hi)


def safe_div(a, b):
    """Element-wise safe division."""
    try:
        result = a / b
        return result.replace([np.inf, -np.inf], np.nan)
    except Exception:
        return np.nan
