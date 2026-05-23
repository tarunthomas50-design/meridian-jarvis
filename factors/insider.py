"""
Factor 7 — Insider Activity (3 sub-factors)
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import sqlite3

from factors.utils import pct_rank_within_sector

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH


def compute_insider(tickers: list[str], sector_map: pd.Series, days: int = 90) -> pd.DataFrame:
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    try:
        conn = sqlite3.connect(DB_PATH)
        ph = ",".join("?" * len(tickers))
        df = pd.read_sql(
            f"""SELECT ticker, transaction_code, value, is_ceo_cfo, insider_name, date
                FROM insider_transactions
                WHERE ticker IN ({ph}) AND date >= ?""",
            conn, params=tickers + [cutoff]
        )
        conn.close()
    except Exception:
        df = pd.DataFrame()

    sub = pd.DataFrame(index=tickers)
    sub["net_dollar_flow"] = 0.0
    sub["ceo_cfo_buy"] = 0.0
    sub["cluster_buy"] = 0.0

    if not df.empty:
        for tk in tickers:
            t = df[df["ticker"] == tk]
            if t.empty:
                continue
            buys = t[t["transaction_code"] == "P"]["value"].fillna(0).sum()
            sells = t[t["transaction_code"] == "S"]["value"].fillna(0).sum()
            # CEO/CFO purchases weighted 3x
            ceo_buys = t[(t["transaction_code"] == "P") & (t["is_ceo_cfo"] == 1)]["value"].fillna(0).sum()
            net = buys * 1.0 + ceo_buys * 2.0 - sells  # CEO buys count 3x total (1 + 2 bonus)
            sub.loc[tk, "net_dollar_flow"] = net

            sub.loc[tk, "ceo_cfo_buy"] = float(ceo_buys > 0)

            # Cluster buy: 3+ insiders buying in last 30 days
            recent = t[t["date"] >= (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")]
            buyers = recent[recent["transaction_code"] == "P"]["insider_name"].nunique()
            sub.loc[tk, "cluster_buy"] = float(buyers >= 3)

    sm = sector_map.loc[tickers]
    scored = pd.DataFrame(index=tickers)
    for col in sub.columns:
        scored[col] = pct_rank_within_sector(sub[col], sm)

    scored["insider_score"] = scored.mean(axis=1)
    scored["insider_score"] = pct_rank_within_sector(scored["insider_score"], sm)
    return scored
