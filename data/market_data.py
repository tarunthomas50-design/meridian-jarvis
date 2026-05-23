"""
Layer 1 — Market Data: daily OHLCV + fundamentals via yfinance.
Incremental updates — only fetches new data since last stored date.
"""
import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import numpy as np
import yfinance as yf

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import DB_PATH, LOOKBACK_DAYS, BENCHMARK_TICKERS

logger = logging.getLogger(__name__)


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_prices (
            ticker TEXT,
            date TEXT,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume REAL,
            PRIMARY KEY (ticker, date)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS fundamentals (
            ticker TEXT PRIMARY KEY,
            market_cap REAL,
            pe_ratio REAL,
            pb_ratio REAL,
            ps_ratio REAL,
            ev_ebitda REAL,
            roe REAL,
            roa REAL,
            gross_margin REAL,
            operating_margin REAL,
            net_margin REAL,
            revenue_growth_yoy REAL,
            earnings_growth_yoy REAL,
            debt_equity REAL,
            fcf_yield REAL,
            current_ratio REAL,
            cfo_ni REAL,
            accruals_ratio REAL,
            shares_outstanding REAL,
            dividends_paid REAL,
            buybacks REAL,
            asset_turnover REAL,
            rd_expense REAL,
            revenue REAL,
            net_income REAL,
            ebitda REAL,
            total_assets REAL,
            total_liabilities REAL,
            working_capital REAL,
            retained_earnings REAL,
            beta REAL,
            forward_eps REAL,
            price_target REAL,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()


def _last_stored_date(ticker: str) -> str | None:
    try:
        conn = sqlite3.connect(DB_PATH)
        row = conn.execute(
            "SELECT MAX(date) FROM daily_prices WHERE ticker=?", (ticker,)
        ).fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def fetch_prices(tickers: list[str], batch_size: int = 50) -> int:
    """Fetch incremental OHLCV for tickers. Returns count of rows added."""
    _init_db()
    total = 0
    start_default = (datetime.now() - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    for i in range(0, len(tickers), batch_size):
        batch = tickers[i : i + batch_size]
        # Find earliest last date in batch
        last_dates = {t: _last_stored_date(t) for t in batch}
        start = min(
            (d for d in last_dates.values() if d),
            default=start_default,
        )
        # Add 1 day to avoid re-inserting last row
        if start != start_default:
            start = (datetime.strptime(start, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

        try:
            raw = yf.download(
                batch, start=start, end=datetime.now().strftime("%Y-%m-%d"),
                auto_adjust=True, progress=False, threads=True,
            )
            if raw.empty:
                continue

            # Handle single vs multi-ticker
            if isinstance(raw.columns, pd.MultiIndex):
                records = []
                for tk in batch:
                    if tk not in raw["Close"].columns:
                        continue
                    sub = raw.xs(tk, axis=1, level=1).dropna(subset=["Close"])
                    sub = sub.reset_index()
                    sub.columns = [c.lower() for c in sub.columns]
                    sub["ticker"] = tk
                    records.append(sub[["ticker", "date", "open", "high", "low", "close", "volume"]])
                if records:
                    df = pd.concat(records)
            else:
                df = raw.reset_index()
                df.columns = [c.lower() for c in df.columns]
                df["ticker"] = batch[0]
                df = df[["ticker", "date", "open", "high", "low", "close", "volume"]]

            df["date"] = df["date"].astype(str).str[:10]
            conn = sqlite3.connect(DB_PATH)
            df.to_sql("daily_prices", conn, if_exists="append", index=False,
                      method="replace" if hasattr(conn, "replace") else None)
            # Use INSERT OR REPLACE
            for _, row in df.iterrows():
                conn.execute(
                    "INSERT OR REPLACE INTO daily_prices VALUES (?,?,?,?,?,?,?)",
                    tuple(row)
                )
            conn.commit()
            conn.close()
            total += len(df)
        except Exception as e:
            logger.error(f"Price fetch error for batch starting {batch[0]}: {e}")

    logger.info(f"Fetched {total} price rows")
    return total


def get_prices(ticker: str, days: int = 252) -> pd.DataFrame:
    """Return OHLCV DataFrame for ticker from DB."""
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql(
        "SELECT * FROM daily_prices WHERE ticker=? ORDER BY date DESC LIMIT ?",
        conn, params=(ticker, days)
    )
    conn.close()
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").set_index("date")


def get_prices_multi(tickers: list[str], days: int = 252) -> pd.DataFrame:
    """Return close-price pivot: dates × tickers."""
    conn = sqlite3.connect(DB_PATH)
    placeholders = ",".join("?" * len(tickers))
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    df = pd.read_sql(
        f"SELECT ticker, date, close FROM daily_prices WHERE ticker IN ({placeholders}) AND date >= ?",
        conn, params=tickers + [cutoff]
    )
    conn.close()
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    return df.pivot(index="date", columns="ticker", values="close").sort_index()


def _safe(val):
    try:
        v = float(val)
        return None if (np.isnan(v) or np.isinf(v)) else v
    except Exception:
        return None


def fetch_fundamentals(tickers: list[str]) -> int:
    """Fetch fundamental data via yfinance for each ticker."""
    _init_db()
    count = 0
    for tk in tickers:
        try:
            info = yf.Ticker(tk).info
            if not info or "symbol" not in info:
                continue
            mc = _safe(info.get("marketCap"))
            rev = _safe(info.get("totalRevenue"))
            ni = _safe(info.get("netIncomeToCommon"))
            ebitda = _safe(info.get("ebitda"))
            ta = _safe(info.get("totalAssets"))
            tl = _safe(info.get("totalDebt"))
            cfo = _safe(info.get("operatingCashflow"))
            capex = _safe(info.get("capitalExpenditures"))
            fcf = None
            if cfo and capex:
                fcf = cfo + capex  # capex is negative in yfinance
            fcf_yield = None
            if fcf and mc and mc > 0:
                fcf_yield = fcf / mc

            cfo_ni = None
            if cfo and ni and ni != 0:
                cfo_ni = cfo / ni

            accruals = None
            if ni and cfo and ta and ta > 0:
                accruals = (ni - cfo) / ta

            wc = _safe(info.get("totalCurrentAssets"))
            wc_l = _safe(info.get("totalCurrentLiabilities"))
            working_capital = (wc - wc_l) if wc and wc_l else None

            row = {
                "ticker": tk,
                "market_cap": mc,
                "pe_ratio": _safe(info.get("trailingPE")),
                "pb_ratio": _safe(info.get("priceToBook")),
                "ps_ratio": _safe(info.get("priceToSalesTrailing12Months")),
                "ev_ebitda": _safe(info.get("enterpriseToEbitda")),
                "roe": _safe(info.get("returnOnEquity")),
                "roa": _safe(info.get("returnOnAssets")),
                "gross_margin": _safe(info.get("grossMargins")),
                "operating_margin": _safe(info.get("operatingMargins")),
                "net_margin": _safe(info.get("profitMargins")),
                "revenue_growth_yoy": _safe(info.get("revenueGrowth")),
                "earnings_growth_yoy": _safe(info.get("earningsGrowth")),
                "debt_equity": _safe(info.get("debtToEquity")),
                "fcf_yield": fcf_yield,
                "current_ratio": _safe(info.get("currentRatio")),
                "cfo_ni": cfo_ni,
                "accruals_ratio": accruals,
                "shares_outstanding": _safe(info.get("sharesOutstanding")),
                "dividends_paid": _safe(info.get("dividendRate")),
                "buybacks": _safe(info.get("buybackYield")),
                "asset_turnover": (rev / ta) if rev and ta and ta > 0 else None,
                "rd_expense": _safe(info.get("researchAndDevelopment")),
                "revenue": rev,
                "net_income": ni,
                "ebitda": ebitda,
                "total_assets": ta,
                "total_liabilities": tl,
                "working_capital": working_capital,
                "retained_earnings": _safe(info.get("retainedEarningsQuarterly")),
                "beta": _safe(info.get("beta")),
                "forward_eps": _safe(info.get("forwardEps")),
                "price_target": _safe(info.get("targetMeanPrice")),
                "updated_at": datetime.now().isoformat(),
            }
            conn = sqlite3.connect(DB_PATH)
            cols = ", ".join(row.keys())
            placeholders = ", ".join("?" * len(row))
            conn.execute(
                f"INSERT OR REPLACE INTO fundamentals ({cols}) VALUES ({placeholders})",
                list(row.values())
            )
            conn.commit()
            conn.close()
            count += 1
        except Exception as e:
            logger.warning(f"Fundamentals failed for {tk}: {e}")
    logger.info(f"Updated fundamentals for {count}/{len(tickers)} tickers")
    return count


def get_fundamentals(tickers: list[str] | None = None) -> pd.DataFrame:
    """Return fundamentals DataFrame from DB."""
    conn = sqlite3.connect(DB_PATH)
    if tickers:
        ph = ",".join("?" * len(tickers))
        df = pd.read_sql(f"SELECT * FROM fundamentals WHERE ticker IN ({ph})", conn, params=tickers)
    else:
        df = pd.read_sql("SELECT * FROM fundamentals", conn)
    conn.close()
    return df


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    from data.universe import get_universe
    df = get_universe()
    tickers = df["ticker"].head(20).tolist()
    fetch_prices(tickers)
    fetch_fundamentals(tickers[:5])
    print("Done")
