"""
Factor 3 — Quality (8 sub-factors including Piotroski F-Score & Altman Z-Score)
"""
import logging
import numpy as np
import pandas as pd

from factors.utils import pct_rank_within_sector, winsorize, safe_div

logger = logging.getLogger(__name__)


def _piotroski(f: pd.DataFrame) -> pd.Series:
    """Compute Piotroski F-Score (0-9) from fundamentals."""
    scores = pd.Series(0.0, index=f.index)

    # 1. ROA > 0
    if "roa" in f.columns:
        scores += (f["roa"] > 0).astype(float)

    # 2. CFO > 0
    # We use cfo_ni proxy: if cfo_ni > 0 and net_income > 0, CFO > 0
    if "cfo_ni" in f.columns and "net_income" in f.columns:
        cfo_positive = ((f["cfo_ni"] > 0) & (f["net_income"] > 0))
        scores += cfo_positive.astype(float)

    # 3. Rising ROA (we can't compute YoY easily without history — set 0.5 neutral)
    # 4. Accruals: CFO/TA > ROA  (accruals_ratio captures this)
    if "accruals_ratio" in f.columns:
        scores += (f["accruals_ratio"] < 0).astype(float)  # low accruals = good

    # 5. Falling D/E
    # 6. Rising current ratio
    if "current_ratio" in f.columns:
        scores += (f["current_ratio"] > 1.0).astype(float)

    # 7. No dilution (shares stable — we skip without history)
    # 8. Rising gross margin
    if "gross_margin" in f.columns:
        scores += (f["gross_margin"] > 0.2).astype(float)  # above 20% proxy

    # 9. Rising asset turnover
    if "asset_turnover" in f.columns:
        scores += (f["asset_turnover"] > 0.5).astype(float)

    # Debt/Equity check
    if "debt_equity" in f.columns:
        scores += (f["debt_equity"] < 1.0).fillna(0).astype(float)

    return scores.clip(0, 9)


def _altman_z(f: pd.DataFrame) -> pd.Series:
    """Altman Z-Score: 1.2*(WC/TA)+1.4*(RE/TA)+3.3*(EBIT/TA)+0.6*(MC/TL)+1.0*(Sales/TA)"""
    ta = f.get("total_assets", pd.Series(np.nan, index=f.index))
    wc = f.get("working_capital", pd.Series(np.nan, index=f.index))
    re = f.get("retained_earnings", pd.Series(np.nan, index=f.index))
    ebit_proxy = f.get("ebitda", pd.Series(np.nan, index=f.index))  # EBITDA ≈ EBIT proxy
    mc = f.get("market_cap", pd.Series(np.nan, index=f.index))
    tl = f.get("total_liabilities", pd.Series(np.nan, index=f.index))
    rev = f.get("revenue", pd.Series(np.nan, index=f.index))

    z = (
        1.2 * safe_div(wc, ta).fillna(0)
        + 1.4 * safe_div(re, ta).fillna(0)
        + 3.3 * safe_div(ebit_proxy, ta).fillna(0)
        + 0.6 * safe_div(mc, tl).fillna(0)
        + 1.0 * safe_div(rev, ta).fillna(0)
    )
    return z


def compute_quality(fundamentals: pd.DataFrame, sector_map: pd.Series) -> pd.DataFrame:
    tickers = [t for t in fundamentals.index if t in sector_map.index]
    if not tickers:
        return pd.DataFrame()

    f = fundamentals.loc[tickers].copy()
    sm = sector_map.loc[tickers]

    sub = pd.DataFrame(index=tickers)

    # 1. ROE stability (invert std — we only have one period, use level as proxy)
    sub["roe"] = f.get("roe", pd.Series(np.nan, index=tickers))

    # 2. Gross margin level
    sub["gross_margin"] = f.get("gross_margin", pd.Series(np.nan, index=tickers))

    # 3. Debt/equity (inverted — lower = better)
    de = f.get("debt_equity", pd.Series(np.nan, index=tickers))
    sub["debt_equity_inv"] = safe_div(pd.Series(1.0, index=tickers), de.replace(0, np.nan))

    # 4. CFO/NI (higher = real cash earnings)
    sub["cfo_ni"] = f.get("cfo_ni", pd.Series(np.nan, index=tickers))

    # 5. Accruals ratio (invert — low accruals = high quality)
    accruals = f.get("accruals_ratio", pd.Series(np.nan, index=tickers))
    sub["accruals_inv"] = -accruals  # invert so lower accruals → higher score

    # 6. Piotroski F-Score
    sub["piotroski"] = _piotroski(f)

    # 7. Altman Z-Score
    sub["altman_z"] = _altman_z(f)

    # 8. Operating margin
    sub["operating_margin"] = f.get("operating_margin", pd.Series(np.nan, index=tickers))

    # Rank within sector
    scored = pd.DataFrame(index=tickers)
    for col in sub.columns:
        winsorized = winsorize(sub[col].dropna())
        sub.loc[winsorized.index, col] = winsorized
        scored[col] = pct_rank_within_sector(sub[col], sm)

    scored["quality_score"] = scored.mean(axis=1)
    scored["quality_score"] = pct_rank_within_sector(scored["quality_score"], sm)
    return scored
