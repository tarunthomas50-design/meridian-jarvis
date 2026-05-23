"""
Layer 1 — Universe: S&P 500 tickers from Wikipedia, cached weekly.
"""
import json
import time
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import CACHE_DIR, DB_PATH, BENCHMARK_TICKERS

logger = logging.getLogger(__name__)

UNIVERSE_CACHE = CACHE_DIR / "universe_cache.json"
CACHE_TTL_DAYS = 7


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS universe (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            sector TEXT,
            sub_industry TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def fetch_sp500_wiki() -> pd.DataFrame:
    """Scrape S&P 500 list from Wikipedia."""
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        soup = BeautifulSoup(resp.text, "lxml")
        table = soup.find("table", {"id": "constituents"})
        df = pd.read_html(str(table))[0]
        df = df[["Symbol", "Security", "GICS Sector", "GICS Sub-Industry"]].copy()
        df.columns = ["ticker", "name", "sector", "sub_industry"]
        # BRK.B → BRK-B for yfinance
        df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
        return df
    except Exception as e:
        logger.error(f"Wiki scrape failed: {e}")
        return pd.DataFrame()


def get_universe(force_refresh: bool = False) -> pd.DataFrame:
    """Return S&P 500 universe DataFrame, refreshing weekly."""
    _init_db()

    # Check cache age
    if UNIVERSE_CACHE.exists() and not force_refresh:
        age = datetime.now() - datetime.fromtimestamp(UNIVERSE_CACHE.stat().st_mtime)
        if age < timedelta(days=CACHE_TTL_DAYS):
            with open(UNIVERSE_CACHE) as f:
                data = json.load(f)
            return pd.DataFrame(data)

    logger.info("Refreshing S&P 500 universe from Wikipedia…")
    df = fetch_sp500_wiki()
    if df.empty:
        # Fall back to DB
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql("SELECT * FROM universe", conn)
        conn.close()
        return df

    # Save to cache and DB
    df["updated_at"] = datetime.now().isoformat()
    with open(UNIVERSE_CACHE, "w") as f:
        json.dump(df.to_dict(orient="records"), f)

    conn = sqlite3.connect(DB_PATH)
    df.to_sql("universe", conn, if_exists="replace", index=False)
    conn.commit()
    conn.close()

    logger.info(f"Universe: {len(df)} tickers loaded")
    return df


def get_all_tickers() -> list[str]:
    """Return S&P 500 tickers + benchmark tickers."""
    df = get_universe()
    sp500 = df["ticker"].tolist()
    return list(set(sp500 + BENCHMARK_TICKERS))


def get_sectors() -> dict[str, list[str]]:
    """Return {sector: [tickers]} mapping."""
    df = get_universe()
    return df.groupby("sector")["ticker"].apply(list).to_dict()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    df = get_universe()
    print(f"Universe: {len(df)} stocks")
    print(df.head())
