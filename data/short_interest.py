"""
Layer 1 — Short Interest: shares_short, short_ratio, short_percent_of_float via yfinance.
"""
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import yfinance as yf

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH

logger = logging.getLogger(__name__)


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS short_interest (
            ticker TEXT,
            date TEXT,
            shares_short REAL,
            short_ratio REAL,
            short_pct_float REAL,
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.commit()
    conn.close()


def fetch_short_interest(tickers: list[str]) -> int:
    """Fetch short interest snapshot for tickers."""
    _init_db()
    today = datetime.now().strftime("%Y-%m-%d")
    count = 0
    for tk in tickers:
        try:
            info = yf.Ticker(tk).info
            shares_short = info.get("sharesShort")
            short_ratio = info.get("shortRatio")
            short_pct = info.get("shortPercentOfFloat")
            if shares_short is None:
                continue
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT OR REPLACE INTO short_interest VALUES (?,?,?,?,?)",
                (tk, today, shares_short, short_ratio, short_pct)
            )
            conn.commit()
            conn.close()
            count += 1
        except Exception as e:
            logger.warning(f"Short interest failed for {tk}: {e}")
    return count


def get_short_interest(tickers: list[str]) -> pd.DataFrame:
    """Return latest short interest snapshot per ticker."""
    conn = sqlite3.connect(DB_PATH)
    ph = ",".join("?" * len(tickers))
    df = pd.read_sql(
        f"""SELECT s.* FROM short_interest s
            INNER JOIN (
                SELECT ticker, MAX(date) as max_date FROM short_interest
                WHERE ticker IN ({ph}) GROUP BY ticker
            ) m ON s.ticker=m.ticker AND s.date=m.max_date""",
        conn, params=tickers
    )
    conn.close()
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    n = fetch_short_interest(["AAPL", "TSLA", "NVDA"])
    print(f"Short interest rows: {n}")
    print(get_short_interest(["AAPL", "TSLA", "NVDA"]))
