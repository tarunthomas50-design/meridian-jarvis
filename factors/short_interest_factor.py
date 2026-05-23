"""
Factor 6 — Short Interest (3 sub-factors)
For LONGS: declining short interest scores higher.
For SHORTS: increasing short interest scores higher.
"""
import numpy as np
import pandas as pd

from factors.utils import pct_rank_within_sector


def compute_short_interest(short_df: pd.DataFrame, sector_map: pd.Series,
                           for_longs: bool = True) -> pd.DataFrame:
    """
    short_df: DataFrame with ticker index, columns: short_pct_float, short_ratio
    for_longs=True means lower short interest → better score
    """
    tickers = [t for t in short_df.index if t in sector_map.index]
    if not tickers:
        return pd.DataFrame()

    sub = short_df.loc[tickers].copy()
    sm = sector_map.loc[tickers]
    scored = pd.DataFrame(index=tickers)

    pct_float = sub.get("short_pct_float", pd.Series(np.nan, index=tickers))
    ratio = sub.get("short_ratio", pd.Series(np.nan, index=tickers))

    if for_longs:
        # Lower short interest = higher score → invert
        scored["short_pct_float"] = pct_rank_within_sector(-pct_float.fillna(pct_float.mean()), sm)
        scored["short_ratio"] = pct_rank_within_sector(-ratio.fillna(ratio.mean()), sm)
    else:
        # Higher short interest = higher score (crowded shorts = good short candidates)
        scored["short_pct_float"] = pct_rank_within_sector(pct_float.fillna(pct_float.mean()), sm)
        scored["short_ratio"] = pct_rank_within_sector(ratio.fillna(ratio.mean()), sm)

    scored["si_change"] = 50.0  # neutral until we have prior period data

    scored["short_interest_score"] = scored.mean(axis=1)
    scored["short_interest_score"] = pct_rank_within_sector(scored["short_interest_score"], sm)
    return scored
