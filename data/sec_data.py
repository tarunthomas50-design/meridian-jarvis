"""
Layer 1 — SEC EDGAR: insider transactions (Form 4) + 10-K/10-Q/8-K filing metadata.
Uses EDGAR EFTS full-text search API. Rate limit: 8 req/sec.
"""
import sqlite3
import time
import logging
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from xml.etree import ElementTree as ET

import requests
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, SEC_USER_AGENT, SEC_RATE_LIMIT

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": SEC_USER_AGENT, "Accept-Encoding": "gzip, deflate"}
BASE = "https://efts.sec.gov/LATEST/search-index"
SUBMISSIONS = "https://data.sec.gov/submissions"
_last_call = 0.0


def _rate_limit():
    global _last_call
    gap = 1.0 / SEC_RATE_LIMIT
    wait = gap - (time.time() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.time()


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS insider_transactions (
            id TEXT PRIMARY KEY,
            ticker TEXT,
            insider_name TEXT,
            insider_title TEXT,
            transaction_type TEXT,
            transaction_code TEXT,
            shares REAL,
            price REAL,
            value REAL,
            date TEXT,
            ownership_type TEXT,
            is_ceo_cfo INTEGER,
            updated_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sec_filings (
            accession_number TEXT PRIMARY KEY,
            ticker TEXT,
            form_type TEXT,
            filed_at TEXT,
            description TEXT,
            document_url TEXT
        )
    """)
    conn.commit()
    conn.close()


def _get_cik(ticker: str) -> str | None:
    """Look up CIK for a ticker via SEC company search."""
    try:
        _rate_limit()
        r = requests.get(
            f"https://efts.sec.gov/LATEST/search-index?q=%22{ticker}%22&dateRange=custom"
            f"&startdt=2020-01-01&forms=4",
            headers=HEADERS, timeout=10
        )
        # Alternative: company_tickers.json
        r2 = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=HEADERS, timeout=15
        )
        data = r2.json()
        for _, v in data.items():
            if v["ticker"].upper() == ticker.upper():
                return str(v["cik_str"]).zfill(10)
    except Exception as e:
        logger.warning(f"CIK lookup failed for {ticker}: {e}")
    return None


# Cache CIKs in memory
_cik_cache: dict[str, str] = {}
_ticker_map: dict[str, str] = {}


def _load_ticker_map():
    global _ticker_map
    if _ticker_map:
        return
    try:
        _rate_limit()
        r = requests.get(
            "https://www.sec.gov/files/company_tickers.json",
            headers=HEADERS, timeout=20
        )
        data = r.json()
        _ticker_map = {v["ticker"].upper(): str(v["cik_str"]).zfill(10) for _, v in data.items()}
    except Exception as e:
        logger.error(f"Ticker map load failed: {e}")


def get_cik(ticker: str) -> str | None:
    if ticker in _cik_cache:
        return _cik_cache[ticker]
    _load_ticker_map()
    cik = _ticker_map.get(ticker.upper().replace("-", "."))
    if not cik:
        cik = _ticker_map.get(ticker.upper())
    if cik:
        _cik_cache[ticker] = cik
    return cik


def fetch_form4(ticker: str, days: int = 180) -> list[dict]:
    """Fetch Form 4 insider transactions for ticker via EDGAR."""
    _init_db()
    cik = get_cik(ticker)
    if not cik:
        logger.warning(f"No CIK found for {ticker}")
        return []

    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    results = []

    try:
        _rate_limit()
        url = f"{SUBMISSIONS}/{cik}.json"
        r = requests.get(url, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            return []
        data = r.json()
        filings = data.get("filings", {}).get("recent", {})
        forms = filings.get("form", [])
        acc_nums = filings.get("accessionNumber", [])
        dates = filings.get("filingDate", [])

        form4_indices = [
            i for i, f in enumerate(forms)
            if f in ("4", "4/A") and dates[i] >= cutoff
        ]

        for idx in form4_indices[:30]:  # max 30 filings
            acc = acc_nums[idx].replace("-", "")
            filed = dates[idx]
            _rate_limit()
            xml_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc}/form4.xml"
            try:
                xr = requests.get(xml_url, headers=HEADERS, timeout=10)
                if xr.status_code != 200:
                    continue
                root = ET.fromstring(xr.text)
                ns = ""
                reporter_name = (root.findtext(f"{ns}reportingOwner/{ns}reportingOwnerId/{ns}rptOwnerName") or
                                 root.findtext("reportingOwner/reportingOwnerId/rptOwnerName") or "Unknown")
                title = (root.findtext(f"{ns}reportingOwner/{ns}reportingOwnerRelationship/{ns}officerTitle") or
                         root.findtext("reportingOwner/reportingOwnerRelationship/officerTitle") or "")
                is_officer = root.findtext("reportingOwner/reportingOwnerRelationship/isOfficer") == "1"

                for txn in root.findall(".//nonDerivativeTransaction") + root.findall(".//derivativeTransaction"):
                    code_el = txn.find(".//transactionCode")
                    if code_el is None:
                        continue
                    code = code_el.text or ""
                    if code not in ("P", "S"):  # P=purchase, S=sale only
                        continue

                    shares_el = txn.find(".//transactionShares/value")
                    price_el = txn.find(".//transactionPricePerShare/value")
                    date_el = txn.find(".//transactionDate/value")

                    shares = float(shares_el.text) if shares_el is not None and shares_el.text else 0
                    price = float(price_el.text) if price_el is not None and price_el.text else 0
                    date_str = date_el.text if date_el is not None else filed

                    rec_id = f"{ticker}_{acc}_{code}_{shares}"
                    is_ceo_cfo = int(any(t in title.upper() for t in ["CEO", "CFO", "CHIEF EXECUTIVE", "CHIEF FINANCIAL"]))

                    row = {
                        "id": rec_id,
                        "ticker": ticker,
                        "insider_name": reporter_name,
                        "insider_title": title,
                        "transaction_type": "purchase" if code == "P" else "sale",
                        "transaction_code": code,
                        "shares": shares,
                        "price": price,
                        "value": shares * price,
                        "date": date_str,
                        "ownership_type": "direct",
                        "is_ceo_cfo": is_ceo_cfo,
                        "updated_at": datetime.now().isoformat(),
                    }
                    results.append(row)
            except Exception as xe:
                logger.debug(f"Form4 parse error {acc}: {xe}")

        # Store to DB
        if results:
            conn = sqlite3.connect(DB_PATH)
            for row in results:
                conn.execute(
                    "INSERT OR REPLACE INTO insider_transactions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    list(row.values())
                )
            conn.commit()
            conn.close()

    except Exception as e:
        logger.error(f"Form4 fetch failed for {ticker}: {e}")

    return results


def get_insider_transactions(ticker: str, days: int = 90) -> pd.DataFrame:
    """Return insider transactions from DB for ticker."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT * FROM insider_transactions WHERE ticker=? AND date>=? ORDER BY date DESC",
        conn, params=(ticker, cutoff)
    )
    conn.close()
    return df


def get_cluster_buy_flags(tickers: list[str], days: int = 30) -> dict[str, bool]:
    """Flag tickers where 3+ insiders bought within last N days."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    conn = sqlite3.connect(DB_PATH)
    ph = ",".join("?" * len(tickers))
    df = pd.read_sql(
        f"""SELECT ticker, COUNT(DISTINCT insider_name) as buyers
            FROM insider_transactions
            WHERE ticker IN ({ph}) AND date>=? AND transaction_code='P'
            GROUP BY ticker""",
        conn, params=tickers + [cutoff]
    )
    conn.close()
    flags = {tk: False for tk in tickers}
    for _, row in df.iterrows():
        flags[row["ticker"]] = row["buyers"] >= 3
    return flags


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    rows = fetch_form4("AAPL", days=90)
    print(f"AAPL Form 4: {len(rows)} transactions")
